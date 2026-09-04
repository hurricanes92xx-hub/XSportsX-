#!/usr/bin/env python3
"""Ensure recurring wrestling TV programming is represented when official feeds omit it.

These are FALLBACK schedule templates only. An official/provider event always wins through
identity matching, so this cannot replace a verified date/time with an invented duplicate.
Times are converted from the published U.S. Eastern weekly slot using zoneinfo.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from event_identity import event_identity, identity_match

FEED = Path("data/schedule_feed.json")
ET = ZoneInfo("America/New_York")
UTC = timezone.utc

# Current published weekly U.S. programming. Keep this list deliberately conservative:
# only recurring shows with an authoritative weekly slot are represented here.
WEEKLY = [
    ("WWE", "Monday Night Raw", 0, 20, 0, "Netflix"),
    ("WWE", "NXT", 1, 20, 0, "The CW"),
    ("WWE", "WWE Evolve", 2, 20, 0, "Tubi"),
    ("WWE", "WWE Main Event", 3, 20, 0, "YouTube"),
    ("WWE", "Friday Night SmackDown", 4, 20, 0, "USA"),
    ("AAA Wrestling", "AAA Lucha Libre", 5, 22, 0, "YouTube"),
    ("TNA", "Thursday Night iMPACT!", 3, 21, 0, "AMC"),
    ("AEW", "AEW Dynamite", 2, 20, 0, "TBS / Max"),
    ("AEW", "AEW Collision", 5, 20, 0, "TNT / Max"),
]

# 370 days keeps the app's normal forward schedule horizon populated while avoiding
# an unbounded synthetic calendar.
HORIZON_DAYS = 370
LOOKBACK_HOURS = 12


def _start_utc(day: datetime, hour: int, minute: int) -> str:
    local = datetime(day.year, day.month, day.day, hour, minute, tzinfo=ET)
    return local.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _same_event(events: list[dict], candidate: dict) -> bool:
    return any(identity_match(existing, candidate) for existing in events if isinstance(existing, dict))


def main() -> int:
    if not FEED.exists():
        raise SystemExit("schedule feed missing")
    feed = json.loads(FEED.read_text(encoding="utf-8"))
    events = feed.get("events")
    if not isinstance(events, list):
        raise SystemExit("schedule feed events is not a list")

    now = datetime.now(UTC)
    first_day = now - timedelta(hours=LOOKBACK_HOURS)
    last_day = now + timedelta(days=HORIZON_DAYS)
    added = 0
    by_league: dict[str, int] = {}

    cursor = first_day.astimezone(ET).replace(hour=0, minute=0, second=0, microsecond=0)
    while cursor <= last_day.astimezone(ET):
        for league, title, weekday, hour, minute, network in WEEKLY:
            if cursor.weekday() != weekday:
                continue
            start = _start_utc(cursor, hour, minute)
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            if dt < first_day or dt > last_day:
                continue
            candidate = {
                "id": event_identity(league, title, start),
                "sport": "wrestling",
                "league": league,
                "title": title,
                "startUtc": start,
                "start": start,
                "tag": "UPCOMING",
                "icon": "🤼",
                "source": "weekly-template",
                "scheduleAuthority": "recurring-official-slot",
                "broadcastNetwork": network,
                "weeklyScheduleFallback": True,
            }
            if _same_event(events, candidate):
                continue
            events.append(candidate)
            added += 1
            by_league[league] = by_league.get(league, 0) + 1
        cursor += timedelta(days=1)

    feed["events"] = events
    counts: dict[str, int] = {}
    for event in events:
        league = str(event.get("league") or "").strip()
        if league:
            counts[league] = counts.get(league, 0) + 1
    feed["eventCounts"] = counts
    feed["wrestlingWeeklySchedule"] = {
        "schema": 1,
        "horizonDays": HORIZON_DAYS,
        "fallbackEventsAdded": added,
        "byLeague": by_league,
        "verifiedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "contract": "official/provider events override weekly templates by canonical identity",
    }
    FEED.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrestling weekly schedule: added={added} byLeague={by_league}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
