#!/usr/bin/env python3
"""Autonomous last-mile schedule repair for every configured league.

This is intentionally provider-agnostic: when a configured league has no
near-term canonical event while its season is active, research authoritative
schedule pages, extract structured events, validate them, and merge them into
the canonical feed. Search snippets alone are never promoted to events.
"""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
import refresh_provider_matrix_v3 as core
import provider_discovery as discovery
import sports_web_research as web_research
from season_intelligence import analyze

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data" / "schedule_feed.json"
MAX_LEAGUE_REPAIRS = 24
LOOKAHEAD_DAYS = 7
OFFICIAL_RECOVERY_URLS = {
    "UFC": "https://www.ufc.com/events",
}


def _dt(value: str):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _known_leagues(payload):
    leagues = set()
    matrix = payload.get("leagueProviderMatrix") or {}
    leagues.update(str(x).strip() for x in matrix.keys() if str(x).strip())
    for event in payload.get("events") or []:
        if isinstance(event, dict) and event.get("league"):
            leagues.add(str(event["league"]).strip())
    for league in payload.get("noEventLeagues") or []:
        if league:
            leagues.add(str(league).strip())
    return sorted(leagues)


def _needs_repair(league, events, season_states):
    state = season_states.get(league) or analyze(league, events)
    if not state.get("active"):
        return False, state, "off-season"
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=LOOKAHEAD_DAYS)
    future = []
    for event in events:
        if str(event.get("league", "")).strip() != league:
            continue
        dt = _dt(event.get("startUtc") or event.get("start"))
        if dt and dt >= now - timedelta(hours=2) and dt <= horizon:
            future.append(dt)
    if not future:
        return True, state, "active-league-without-near-term-events"
    return False, state, "covered"


def _parse_ufc_html(url, body):
    """Recover UFC event cards from official HTML when JSON-LD is absent.

    The UFC events page has changed markup several times. Do not depend on a
    single CSS structure: locate event links, then search their local HTML
    neighborhood for an explicit published date/time. Never manufacture a
    time when the page does not publish one.
    """
    if not body or "ufc.com" not in url.lower():
        return []
    text = body.decode("utf-8", "replace")
    out = []
    seen = set()
    now = datetime.now(timezone.utc)
    link_re = re.compile(r'<a[^>]+href=["\']/event/([^"\']+)[^>]*>(.*?)</a>', re.I | re.S)
    date_patterns = [
        re.compile(r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+([A-Z][a-z]{2,9})\s+(\d{1,2}),?\s+(\d{4})', re.I),
        re.compile(r'([A-Z][a-z]{2,9})\s+(\d{1,2}),\s+(\d{4})', re.I),
        re.compile(r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+([A-Z][a-z]{2})\s+(\d{1,2})\s*/\s*(\d{1,2}:\d{2}\s*[AP]M)\s*([A-Z]{2,5})', re.I),
    ]
    time_re = re.compile(r'(\d{1,2}:\d{2}\s*[AP]M|\d{1,2}\s*[AP]M)\s*(ET|EDT|EST|PT|PDT|PST|CT|CDT|CST|MT|MDT|MST|UTC|GMT)?', re.I)
    offsets = {
        "UTC": 0, "GMT": 0, "ET": -5, "EST": -5, "EDT": -4,
        "CT": -6, "CST": -6, "CDT": -5, "MT": -7, "MST": -7,
        "MDT": -6, "PT": -8, "PST": -8, "PDT": -7,
    }
    for match in link_re.finditer(text):
        slug = match.group(1)
        if slug in seen:
            continue
        window = re.sub(r'<[^>]+>', ' ', text[match.start():min(len(text), match.end() + 16000)])
        window = ' '.join(window.split())
        event_date = None
        explicit_time = None
        tz_name = None
        for pattern in date_patterns:
            dm = pattern.search(window)
            if not dm:
                continue
            groups = dm.groups()
            try:
                if len(groups) == 4 and ':' in groups[2]:
                    month, day, clock, tz = groups
                    year = now.year
                    event_date = datetime.strptime(f"{month} {day} {year}", "%b %d %Y").date()
                    explicit_time, tz_name = clock, tz
                else:
                    month, day, year = groups[:3]
                    event_date = datetime.strptime(f"{month} {day} {year}", "%B %d %Y").date()
            except ValueError:
                try:
                    event_date = datetime.strptime(f"{month} {day} {year}", "%b %d %Y").date()
                except Exception:
                    event_date = None
            if event_date:
                break
        if not event_date:
            continue
        if not explicit_time:
            tm = time_re.search(window)
            if tm:
                explicit_time, tz_name = tm.group(1), tm.group(2)
        if not explicit_time:
            # Date-only cards are not safe enough to become timed schedule events.
            continue
        tz_name = (tz_name or "ET").upper()
        if tz_name not in offsets:
            continue
        try:
            clock = explicit_time.upper().replace(" ", "")
            parsed = datetime.strptime(clock, "%I:%M%p") if ":" in clock else datetime.strptime(clock, "%I%p")
            local = datetime(event_date.year, event_date.month, event_date.day, parsed.hour, parsed.minute, tzinfo=timezone(timedelta(hours=offsets[tz_name])))
            start = local.astimezone(timezone.utc)
        except Exception:
            continue
        if start < now - timedelta(hours=12):
            continue
        title_match = re.search(r'(?:Fight Night|UFC\s*\d+|UFC\s*Fight\s*Night)[^<]{0,180}', window, re.I)
        title = ' '.join((title_match.group(0) if title_match else slug.replace('-', ' ')).split()).strip()
        if not title:
            continue
        out.append({
            "sport": "MMA",
            "league": "UFC",
            "title": title,
            "startUtc": start.isoformat().replace("+00:00", "Z"),
            "start": start.isoformat().replace("+00:00", "Z"),
            "status": "scheduled",
            "state": "",
            "source": "official-html",
            "discoveryUrl": url,
        })
        seen.add(slug)
    return out[:50]


def _validated_events(league, result):
    url = str(result.get("url") or "")
    if not url or float(result.get("score", 0)) < 0.70:
        return []
    body, ctype, _ = discovery._get(url, timeout=5)
    if not body:
        return []
    extracted = []
    for raw in discovery._extract_events(body, ctype, league):
        if str(raw.get("league", "")).strip() != league:
            continue
        start = _dt(raw.get("startUtc") or raw.get("start"))
        if not start:
            continue
        raw["source"] = "google-discovery"
        raw["discoveryUrl"] = url
        raw["discoveryConfidence"] = float(result.get("score", 0))
        raw["scheduleRepair"] = True
        extracted.append(raw)
    if league.upper() == "UFC":
        extracted.extend(_parse_ufc_html(url, body))
    return extracted


def _recover_official(league):
    url = OFFICIAL_RECOVERY_URLS.get(league.upper())
    if not url:
        return []
    body, ctype, _ = discovery._get(url, timeout=6)
    if not body:
        return []
    recovered = discovery._extract_events(body, ctype, league)
    if league.upper() == "UFC":
        recovered.extend(_parse_ufc_html(url, body))
    valid = []
    now = datetime.now(timezone.utc)
    for raw in recovered:
        start = _dt(raw.get("startUtc") or raw.get("start"))
        if not raw.get("title") or not start or start < now - timedelta(hours=12):
            continue
        raw["league"] = league
        raw["source"] = "official-recovery"
        raw["discoveryUrl"] = url
        raw["discoveryConfidence"] = 1.0
        raw["scheduleRepair"] = True
        valid.append(raw)
    return valid


def main():
    if not FEED.exists():
        raise SystemExit("ERROR: schedule feed does not exist")
    payload = json.loads(FEED.read_text(encoding="utf-8"))
    events = [e for e in (payload.get("events") or []) if isinstance(e, dict)]
    season_states = {}
    repair_candidates = []
    for league in _known_leagues(payload):
        needed, state, reason = _needs_repair(league, events, season_states)
        season_states[league] = state
        if needed:
            repair_candidates.append((league, reason))
    explicit = {str(x) for x in (payload.get("noEventLeagues") or [])}
    repair_candidates.sort(key=lambda x: (0 if x[0] in explicit else 1, x[0]))
    repaired = []
    research_count = 0
    searched = []
    for league, reason in repair_candidates[:MAX_LEAGUE_REPAIRS]:
        searched.append(league)
        official = _recover_official(league)
        if official:
            repaired.extend(official)
            continue
        results = web_research.research_schedule(league, limit=10)
        research_count += len(results)
        for result in results:
            recovered = _validated_events(league, result)
            if recovered:
                repaired.extend(recovered)
                break
    merges = 0
    if repaired:
        canonical, merges, _ = core.dedupe(events + repaired)
        canonical.sort(key=lambda e: e.get("start") or e.get("startUtc") or "")
        payload["events"] = canonical
        events = canonical
    remaining = []
    for league, _ in repair_candidates:
        if not any(str(e.get("league", "")).strip() == league for e in events):
            remaining.append(league)
    payload["autonomousScheduleRepair"] = {
        "enabled": True,
        "leaguesChecked": len(_known_leagues(payload)),
        "repairCandidates": len(repair_candidates),
        "searchedLeagues": len(searched),
        "researchResults": research_count,
        "eventsRecovered": len(repaired),
        "identityMerges": merges,
        "unresolvedLeagues": remaining,
        "updatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "policy": "active configured league with no canonical event in the next 7 days triggers authoritative recovery before secondary research; search snippets are never canonical truth",
    }
    tmp = FEED.with_suffix(".repair.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(FEED)
    print("AUTONOMOUS_SCHEDULE_REPAIR: " + json.dumps(payload["autonomousScheduleRepair"], separators=(",", ":")))

if __name__ == "__main__":
    main()
