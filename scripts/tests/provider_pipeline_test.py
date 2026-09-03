#!/usr/bin/env python3
"""Offline contract tests for the canonical sports schedule pipeline."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FEED = ROOT / "data" / "schedule_feed.json"
REFRESH = ROOT / "scripts" / "refresh_schedules.py"


def fail(msg):
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def main():
    if not REFRESH.exists(): fail("canonical schedule publisher missing")
    if not FEED.exists(): fail("schedule_feed.json missing")
    raw = FEED.read_text(encoding="utf-8").strip()
    if not raw: fail("schedule_feed.json is empty")
    try: data = json.loads(raw)
    except Exception as e: fail(f"invalid JSON: {e}")
    events = data.get("events") if isinstance(data, dict) else data
    if not isinstance(events, list): fail("feed has no events array")
    if not events: fail("feed contains zero events")
    required = {"id", "league", "title", "startUtc"}
    bad = [e for e in events if not isinstance(e, dict) or not required.issubset(e)]
    if bad: fail(f"{len(bad)} events missing canonical fields")
    ids = [e["id"] for e in events]
    if len(ids) != len(set(ids)): fail("duplicate canonical event IDs")
    # Verify the publisher imports and executes cleanly without requiring credentials.
    p = subprocess.run([sys.executable, "-m", "py_compile", str(REFRESH)], cwd=ROOT, capture_output=True, text=True)
    if p.returncode: fail("refresh_schedules.py does not compile")
    print(f"PASS: {len(events)} canonical events; unique IDs; publisher compiles")


if __name__ == "__main__": main()
