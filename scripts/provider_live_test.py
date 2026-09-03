#!/usr/bin/env python3
"""End-to-end provider contract test used by CI.

It executes the same publisher path used in production, normalizes the feed,
then applies the hard integrity gate. Live count is reported but is not used as
a hard failure because CI may run outside a live game window.
"""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(*args):
    subprocess.run([PYTHON, *map(str, args)], cwd=ROOT, check=True)


run(ROOT / "scripts" / "refresh_schedules.py")
run(ROOT / "scripts" / "normalize_schedule_feed.py")
run(ROOT / "scripts" / "validate_schedule_integrity.py")

data = json.loads((ROOT / "data" / "schedule_feed.json").read_text(encoding="utf-8"))
events = data.get("events") or []
if not events:
    raise SystemExit("PROVIDER TEST FAIL: canonical feed is empty")

print("=== XSportsX CANONICAL PROVIDER LIVE TEST ===")
print(f"schema={data.get('schema')}")
print(f"canonical_events={len(events)}")
print(f"identity_merges={data.get('identityMergeCount', 0)}")
print(f"provider_counts={json.dumps(data.get('sourceRecordCounts', {}), sort_keys=True)}")
print(f"failed_sources={json.dumps(data.get('failedSources', []), sort_keys=True)}")
print(f"provider_failures={json.dumps(data.get('providerFailures', []), sort_keys=True)}")


def is_live(event):
    values = {
        str(event.get("status", "")).lower(),
        str(event.get("state", "")).lower(),
        str(event.get("lifecycle", "")).lower(),
        str(event.get("tag", "")).lower(),
    }
    return bool(values & {"live", "in_progress", "in-progress", "live_confirmed"}) or any(
        "live" in value or "in progress" in value for value in values
    )


live = [event for event in events if is_live(event)]
print(f"live_events={len(live)}")
for event in sorted(live, key=lambda x: (str(x.get("startUtc", "")), str(x.get("league", "")), str(x.get("title", "")))):
    print(json.dumps({
        key: event.get(key)
        for key in (
            "id", "sport", "league", "title", "home", "away", "startUtc",
            "status", "state", "lifecycle", "source", "tag", "broadcast",
        )
        if event.get(key) is not None
    }, sort_keys=True))
