#!/usr/bin/env python3
"""Post-refresh normalization for known source endpoint drift.

NASCAR is owned by official_api_adapters.py now, so this step deliberately does
not call the legacy NASCAR endpoint. That prevents the old 401/missing-token
path from running before the authoritative adapter.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data" / "schedule_feed.json"

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

def main():
    payload = json.loads(FEED.read_text(encoding="utf-8"))
    events = payload.get("events") or []
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

    payload["events"] = events
    payload["eventCounts"] = {
        k: sum(1 for e in events if e.get("league") == k)
        for k in sorted({e.get("league") for e in events if e.get("league")})
    }
    payload["generatedAt"] = datetime.now(timezone.utc).isoformat()
    payload.setdefault("repairReport", {})
    payload["repairReport"].update({
        "nascarAdded": 0,
        "timestampsNormalized": changed,
        "invalidTimestamps": invalid,
        "legacyNascarRepairDisabled": True,
    })
    FEED.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"schedule normalization complete: timestamps_normalized={changed}, invalid={invalid}; legacy NASCAR repair skipped")
    if invalid:
        raise SystemExit(f"invalid event timestamps remain: {invalid}")

if __name__ == "__main__":
    main()
