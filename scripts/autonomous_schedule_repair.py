#!/usr/bin/env python3
"""Autonomous last-mile schedule repair for every configured league.

This is intentionally provider-agnostic: when a configured league has no
near-term canonical event while its season is active, research authoritative
schedule pages, extract structured events, validate them, and merge them into
the canonical feed. Search snippets alone are never promoted to events.
"""
from __future__ import annotations
import json
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
    return extracted

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
    # Prioritize explicit no-event leagues, then process a bounded batch so a
    # broken provider cannot turn one audit into an unbounded web crawl.
    explicit = {str(x) for x in (payload.get("noEventLeagues") or [])}
    repair_candidates.sort(key=lambda x: (0 if x[0] in explicit else 1, x[0]))
    repaired = []
    research_count = 0
    searched = []
    for league, reason in repair_candidates[:MAX_LEAGUE_REPAIRS]:
        searched.append(league)
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
        "policy": "active configured league with no canonical event in the next 7 days triggers authoritative web research and structured-event validation",
    }
    tmp = FEED.with_suffix(".repair.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(FEED)
    print("AUTONOMOUS_SCHEDULE_REPAIR: " + json.dumps(payload["autonomousScheduleRepair"], separators=(",", ":")))

if __name__ == "__main__":
    main()
