#!/usr/bin/env python3
"""Post-refresh source repair that preserves the canonical engine's full feed.

This intentionally runs AFTER refresh_schedules_engine.py rather than replacing
it. The engine's season-aware preservation remains authoritative; this script
only repairs sources with known endpoint drift and normalizes timestamps.
"""
from __future__ import annotations
import json
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data" / "schedule_feed.json"
HEADERS = {
    "User-Agent": "XSportsX-Schedule/3.1",
    "Accept": "application/json, text/plain, */*",
}

def fetch_json(url: str):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))

def walk(value):
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from walk(v)

def normalize(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for candidate in (text, text.replace("Z", "+00:00"), text.replace("z", "+00:00")):
        try:
            return datetime.fromisoformat(candidate).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            pass
    for fmt in ("%m/%d/%YT%H:%M:%SZ", "%m/%d/%YT%H:%M:%S%z", "%m/%d/%YT%H:%M:%S", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            pass
    return None

def repair_nascar(events, league, series_id):
    year = datetime.now(timezone.utc).year
    url = f"https://feed.nascar.com/api/weekendschedule?series_id={series_id}&race_season={year}&v=1"
    try:
        root = fetch_json(url)
    except Exception as exc:
        print(f"WARNING NASCAR {league}: {exc}")
        return 0
    now = datetime.now(timezone.utc) - timedelta(hours=12)
    horizon = datetime.now(timezone.utc) + timedelta(days=370)
    existing = {(e.get("league"), e.get("title"), e.get("start")) for e in events}
    added = 0
    for obj in walk(root):
        if not isinstance(obj, dict) or obj.get("series_id") != series_id:
            continue
        dt = normalize(obj.get("start_time_utc") or obj.get("start_time"))
        if not dt:
            continue
        parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        if parsed < now or parsed > horizon:
            continue
        event_name = str(obj.get("event_name") or "NASCAR event").strip()
        race_name = str(obj.get("race_name") or "").strip()
        track = str(obj.get("track_name") or "").strip()
        title = race_name or event_name
        if event_name.lower() not in title.lower() and event_name:
            title = f"{title} — {event_name}"
        if track and track.lower() not in title.lower():
            title = f"{title} — {track}"
        key = (league, title, dt)
        if key in existing:
            continue
        existing.add(key)
        run_type = int(obj.get("run_type") or 0)
        tag = "LIVE" if run_type == 3 and parsed <= datetime.now(timezone.utc) else "UPCOMING"
        events.append({"league": league, "title": title, "start": dt, "tag": tag, "icon": "🏎️", "source": "nascar-api"})
        added += 1
    print(f"NASCAR repaired {league}: +{added} events")
    return added

def main():
    payload = json.loads(FEED.read_text(encoding="utf-8"))
    events = payload.get("events") or []
    added = repair_nascar(events, "NASCAR Xfinity", 2) + repair_nascar(events, "NASCAR Truck", 3)

    invalid = 0
    changed = 0
    for event in events:
        raw = event.get("start")
        value = normalize(raw)
        if value is None:
            invalid += 1
            continue
        if raw != value:
            event["start"] = value
            changed += 1

    # Successful direct repairs mean the corresponding official failure should
    # no longer be reported as an unresolved source failure.
    failures = list(payload.get("officialSourceFailures") or [])
    if added:
        failures = [x for x in failures if x not in ("NASCAR Xfinity", "NASCAR Truck")]
        payload["officialSourceFailures"] = failures
    payload["events"] = events
    payload["eventCounts"] = {k: sum(1 for e in events if e.get("league") == k) for k in sorted({e.get("league") for e in events if e.get("league")})}
    payload["generatedAt"] = datetime.now(timezone.utc).isoformat()
    payload.setdefault("repairReport", {})
    payload["repairReport"].update({"nascarAdded": added, "timestampsNormalized": changed, "invalidTimestamps": invalid})
    FEED.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"schedule repair complete: nascar_added={added}, timestamps_normalized={changed}, invalid={invalid}, total={len(events)}")
    if invalid:
        raise SystemExit(f"invalid event timestamps remain: {invalid}")

if __name__ == "__main__":
    main()
