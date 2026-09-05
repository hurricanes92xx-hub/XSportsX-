#!/usr/bin/env python3
"""Validate provider/live-state data before publishing the canonical feed.

A provider can return an ``in``/LIVE flag for an event whose scheduled start is
still in the future. That must never reach Android as a LIVE event. This gate
also records a compact health report and fails the rebuild when impossible live
states remain after normalization.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data" / "schedule_feed.json"
REPORT = ROOT / "data" / "provider_health_gate.json"


def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def is_live(event):
    return (
        str(event.get("tag", "")).upper() == "LIVE"
        or str(event.get("status", "")).upper() == "LIVE"
        or str(event.get("state", "")).lower() == "in"
    )


def set_upcoming(event):
    event["tag"] = "UPCOMING"
    event["status"] = "UPCOMING"
    event["state"] = "pre"
    event["liveStateSource"] = "provider-health-gate"


def main():
    if not FEED.exists():
        raise SystemExit("provider health gate: missing schedule_feed.json")
    payload = json.loads(FEED.read_text(encoding="utf-8"))
    events = [e for e in (payload.get("events") or []) if isinstance(e, dict)]
    now = datetime.now(timezone.utc)
    future_live = []
    stale_live = []

    for event in events:
        if not is_live(event):
            continue
        start = parse_dt(event.get("startUtc") or event.get("start"))
        if start and start > now + __import__("datetime").timedelta(minutes=2):
            future_live.append({"league": event.get("league"), "title": event.get("title"), "startUtc": event.get("startUtc") or event.get("start")})
            set_upcoming(event)

    # Never allow a live record with an obviously invalid/missing start to be
    # published. Missing start data cannot be safely classified as live.
    for event in events:
        if is_live(event) and not parse_dt(event.get("startUtc") or event.get("start")):
            stale_live.append({"league": event.get("league"), "title": event.get("title"), "reason": "missing_start"})
            set_upcoming(event)

    report = {
        "schema": 1,
        "checkedAtUtc": now.isoformat().replace("+00:00", "Z"),
        "eventCount": len(events),
        "futureLiveCorrected": len(future_live),
        "missingStartLiveCorrected": len(stale_live),
        "providerFailures": payload.get("providerFailures") or payload.get("failedSources") or [],
        "failedLiveStates": future_live + stale_live,
    }
    payload["events"] = events
    payload["providerHealthGate"] = report
    FEED.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))

    # Correct bad states automatically; fail only if a malformed LIVE state
    # somehow remains. This protects publishing without making transient
    # provider outages block the entire schedule.
    remaining = [e for e in events if is_live(e) and parse_dt(e.get("startUtc") or e.get("start")) and parse_dt(e.get("startUtc") or e.get("start")) > now + __import__("datetime").timedelta(minutes=2)]
    if remaining:
        raise SystemExit(f"provider health gate: {len(remaining)} impossible future LIVE events remain")


if __name__ == "__main__":
    main()
