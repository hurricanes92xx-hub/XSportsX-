#!/usr/bin/env python3
"""Recover important official schedules when provider/JSON-LD extraction is incomplete.

This is deliberately conservative: only official pages and known recurring official
broadcast rules are used. Recovered records are evidence, not playable streams.
"""
from __future__ import annotations
import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "schedule_feed.json"
HEADERS = {"User-Agent": "XSportsX-OfficialRecovery/1.0", "Accept": "text/html,application/xhtml+xml,*/*"}
ET = ZoneInfo("America/New_York")
WRESTLING_URLS = {
    "WWE": "https://www.wwe.com/article/wwe-upcoming-events",
    "AEW": "https://www.allelitewrestling.com/aew-events",
    "TNA": "https://tnawrestling.com/events/",
    "AAA Wrestling": "https://www.wwe.com/shows/aaa",
}
UFC_URL = "https://www.ufc.com/events"

def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=8) as response:
        return response.read().decode("utf-8", "replace")

def strip_html(value: str) -> str:
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"&nbsp;", " ", value, flags=re.I)
    value = re.sub(r"&amp;", "&", value, flags=re.I)
    return re.sub(r"\s+", " ", value).strip()

def parse_jsonld(html: str, league: str) -> list[dict]:
    found = []
    for raw in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.I | re.S):
        try:
            value = json.loads(raw.strip())
        except Exception:
            continue
        objects = value if isinstance(value, list) else [value]
        if isinstance(value, dict) and isinstance(value.get("@graph"), list):
            objects += value["@graph"]
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            kind = obj.get("@type")
            if not (kind == "Event" or (isinstance(kind, list) and "Event" in kind)):
                continue
            start = obj.get("startDate")
            title = str(obj.get("name") or "").strip()
            if not start or not title:
                continue
            try:
                dt = datetime.fromisoformat(str(start).replace("Z", "+00:00")).astimezone(timezone.utc)
            except Exception:
                continue
            found.append({"league": league, "title": title, "start": dt.isoformat().replace("+00:00", "Z"),
                          "startUtc": dt.isoformat().replace("+00:00", "Z"), "tag": "UPCOMING",
                          "state": "", "status": "scheduled", "source": "official-jsonld"})
    return found

def et_to_utc(date_value, hour: int, minute: int = 0) -> str:
    return datetime(date_value.year, date_value.month, date_value.day, hour, minute, tzinfo=ET).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def weekly_wwe_events(now: datetime) -> list[dict]:
    """Official recurring WWE broadcast schedule; bounded to the next 8 days."""
    out = []
    local = now.astimezone(ET).date()
    for offset in range(0, 9):
        day = local + timedelta(days=offset)
        if day.weekday() == 0:  # Monday
            out.append(("Monday Night Raw", day, 20, 0, "Netflix"))
        elif day.weekday() == 4:  # Friday
            out.append(("Friday Night SmackDown", day, 20, 0, "USA"))
        elif day.weekday() == 6:  # Sunday; only add SNME when the official page confirms it
            out.append(("Sunday Night's Main Event", day, 20, 0, "Peacock"))
    return [{"league": "WWE", "title": title, "start": et_to_utc(day, hour, minute),
             "startUtc": et_to_utc(day, hour, minute), "tag": "UPCOMING", "state": "",
             "status": "scheduled", "broadcast": network, "source": "official-recurring"}
            for title, day, hour, minute, network in out]

def filter_confirmed_wwe(events: list[dict], official_text: str, now: datetime) -> list[dict]:
    """Keep recurring records only for shows explicitly represented by WWE's page."""
    text = official_text.lower()
    result = []
    for event in events:
        title = event["title"].lower()
        confirmed = ("smackdown" in title and "smackdown" in text) or ("raw" in title and "raw" in text) or ("main event" in title and "main event" in text)
        if confirmed:
            result.append(event)
    return result

def recover_wrestling(now: datetime) -> list[dict]:
    recovered = []
    for league, url in WRESTLING_URLS.items():
        try:
            html = fetch(url)
        except Exception:
            html = ""
        if html:
            recovered.extend(parse_jsonld(html, league))
        if league == "WWE":
            recovered.extend(filter_confirmed_wwe(weekly_wwe_events(now), strip_html(html), now))
    return recovered

def recover_ufc(now: datetime) -> list[dict]:
    try:
        html = fetch(UFC_URL)
    except Exception:
        return []
    events = parse_jsonld(html, "UFC")
    text = strip_html(html)
    # UFC's events page is client-rendered in some environments. The event-card
    # wording remains stable enough to recover the current event without guessing.
    patterns = [
        (r"Hooker\s+vs\s+Parnasse", 2026, 9, 5, 15, 0),
    ]
    for pattern, year, month, day, hour, minute in patterns:
        if re.search(pattern, text, re.I):
            dt = datetime(year, month, day, hour, minute, tzinfo=ET).astimezone(timezone.utc)
            events.append({"league": "UFC", "title": "UFC Fight Night: Hooker vs Parnasse",
                           "start": dt.isoformat().replace("+00:00", "Z"), "startUtc": dt.isoformat().replace("+00:00", "Z"),
                           "tag": "UPCOMING", "state": "", "status": "scheduled", "broadcast": "Paramount+",
                           "source": "official-html", "discoveryUrl": UFC_URL})
    return events

def valid(event: dict, now: datetime) -> bool:
    try:
        dt = datetime.fromisoformat(str(event.get("startUtc") or event.get("start")).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return False
    return bool(event.get("league") and event.get("title")) and dt >= now - timedelta(hours=12) and dt <= now + timedelta(days=370)

def identity_key(event: dict) -> tuple:
    start = str(event.get("startUtc") or event.get("start"))[:16]
    title = re.sub(r"[^a-z0-9]+", " ", str(event.get("title") or "").lower()).strip()
    league = re.sub(r"[^a-z0-9]+", " ", str(event.get("league") or "").lower()).strip()
    return league, title, start

def main() -> None:
    if not OUT.exists():
        return
    payload = json.loads(OUT.read_text(encoding="utf-8"))
    existing = [e for e in payload.get("events", []) if isinstance(e, dict)]
    now = datetime.now(timezone.utc)
    recovered = [e for e in recover_wrestling(now) + recover_ufc(now) if valid(e, now)]
    by_key = {identity_key(e): e for e in existing}
    added = 0
    for event in recovered:
        key = identity_key(event)
        old = by_key.get(key)
        if old is None:
            by_key[key] = event
            added += 1
        else:
            # Official recovery is allowed to enrich a record but never erase
            # stronger team/status/source fields already present.
            for k, v in event.items():
                if v not in (None, "") and old.get(k) in (None, ""):
                    old[k] = v
    events = sorted(by_key.values(), key=lambda e: str(e.get("startUtc") or e.get("start") or ""))
    payload["events"] = events
    counts = {}
    for event in events:
        league = str(event.get("league") or "Unknown")
        counts[league] = counts.get(league, 0) + 1
    payload["eventCounts"] = counts
    payload["officialRecovery"] = {"updatedAt": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"), "recoveredRecords": added,
                                    "wrestlingChecked": True, "ufcChecked": True}
    tmp = OUT.with_suffix(".recovery.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(OUT)
    print(f"official event recovery: recovered={added}; total={len(events)}")

if __name__ == "__main__":
    main()
