#!/usr/bin/env python3
"""Run the canonical provider refresh without timestamp-only feed churn."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data" / "schedule_feed.json"

def event_fingerprint(payload):
    return sorted(json.dumps(e, sort_keys=True, ensure_ascii=False) for e in (payload.get("events") or []))

def main():
    before = {}
    if FEED.exists():
        try: before = json.loads(FEED.read_text(encoding="utf-8"))
        except Exception: pass
    subprocess.run(["python3", str(ROOT / "scripts" / "refresh_schedules.py")], cwd=ROOT, check=True)
    subprocess.run(["python3", str(ROOT / "scripts" / "normalize_schedule_feed.py")], cwd=ROOT, check=True)
    try: after = json.loads(FEED.read_text(encoding="utf-8"))
    except Exception: after = {}
    if event_fingerprint(before) == event_fingerprint(after) and before:
        FEED.write_text(json.dumps(before, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("No canonical event changes; restored previous feed.")
    else: print("Canonical event set changed; keeping refreshed feed.")

if __name__ == "__main__": main()
