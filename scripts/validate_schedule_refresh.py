#!/usr/bin/env python3
"""Fail closed when a schedule refresh catastrophically loses coverage."""
import json
from pathlib import Path

FEED = Path("data/schedule_feed.json")
if not FEED.exists():
    raise SystemExit("schedule feed missing")
root = json.loads(FEED.read_text(encoding="utf-8"))
events = root.get("events") or []
counts = root.get("eventCounts") or {}
failed = root.get("failedSources") or []

# A provider outage must never turn a populated feed into an empty/near-empty
# feed. The refresh job can preserve the previous feed for failed leagues.
if not events:
    raise SystemExit("REFRESH REJECTED: schedule feed has zero events")
if len(failed) >= 8 and len(events) < 100:
    raise SystemExit(f"REFRESH REJECTED: {len(failed)} sources failed and only {len(events)} events remain")

# Keep NCAA sports visible when their upstream is returning data.
for league, minimum in (("NCAA Men's Soccer", 1), ("NCAA Women's Soccer", 1), ("NCAA Women's Volleyball", 1)):
    if league in counts and counts[league] < minimum:
        raise SystemExit(f"REFRESH REJECTED: {league} unexpectedly empty")

print(f"schedule refresh accepted: {len(events)} events, {len(counts)} leagues, {len(failed)} failed sources")
