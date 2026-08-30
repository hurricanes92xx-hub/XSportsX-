#!/usr/bin/env python3
"""Fail closed when a schedule refresh loses coverage or silently truncates leagues."""
import json
from datetime import datetime, timezone
from pathlib import Path

FEED = Path("data/schedule_feed.json")
if not FEED.exists():
    raise SystemExit("schedule feed missing")
root = json.loads(FEED.read_text(encoding="utf-8"))
events = root.get("events") or []
counts = root.get("eventCounts") or {}
failed = root.get("failedSources") or []

if not events:
    raise SystemExit("REFRESH REJECTED: schedule feed has zero events")
if len(failed) >= 8 and len(events) < 100:
    raise SystemExit(f"REFRESH REJECTED: {len(failed)} sources failed and only {len(events)} events remain")

# The publication step must not claim more events than it actually writes.
# This catches the old per-league [:400] truncation immediately.
written_counts = {}
for event in events:
    league = event.get("league")
    if not league:
        raise SystemExit("REFRESH REJECTED: event without league")
    start = event.get("start")
    try:
        datetime.fromisoformat(str(start).replace("Z", "+00:00"))
    except Exception:
        raise SystemExit(f"REFRESH REJECTED: malformed start timestamp for {league}: {start!r}")
    written_counts[league] = written_counts.get(league, 0) + 1

for league, expected in counts.items():
    actual = written_counts.get(league, 0)
    if actual != expected:
        raise SystemExit(f"REFRESH REJECTED: {league} count says {expected}, feed contains {actual}")

keys = [(e.get("league"), e.get("title"), e.get("start")) for e in events]
if len(keys) != len(set(keys)):
    raise SystemExit("REFRESH REJECTED: duplicate schedule events detected")

for league, minimum in (("NCAA Men's Soccer", 1), ("NCAA Women's Soccer", 1), ("NCAA Women's Volleyball", 1)):
    if league in counts and counts[league] < minimum:
        raise SystemExit(f"REFRESH REJECTED: {league} unexpectedly empty")

try:
    generated = datetime.fromisoformat(str(root.get("generatedAt")).replace("Z", "+00:00"))
    age_hours = (datetime.now(timezone.utc) - generated.astimezone(timezone.utc)).total_seconds() / 3600
    if age_hours > 30:
        raise SystemExit(f"REFRESH REJECTED: schedule feed is {age_hours:.1f}h old")
except SystemExit:
    raise
except Exception:
    raise SystemExit("REFRESH REJECTED: malformed generatedAt")

print(f"schedule refresh accepted: {len(events)} events, {len(counts)} leagues, {len(failed)} failed sources; no truncation detected")
