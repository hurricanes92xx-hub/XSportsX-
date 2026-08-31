#!/usr/bin/env python3
"""Fail closed when a schedule refresh loses coverage, truncates leagues, or publishes stale Phase 1 repairs."""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

FEED = Path("data/schedule_feed.json")
POLICY = Path("data/schedule_season_policy.json")
REFERENCE_DATE = datetime(2026, 8, 31, tzinfo=timezone.utc)
LOOKAHEAD_DAYS = 370

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
parsed_starts = {}
for event in events:
    league = event.get("league")
    if not league:
        raise SystemExit("REFRESH REJECTED: event without league")
    start = event.get("start")
    try:
        parsed = datetime.fromisoformat(str(start).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        raise SystemExit(f"REFRESH REJECTED: malformed start timestamp for {league}: {start!r}")
    written_counts[league] = written_counts.get(league, 0) + 1
    parsed_starts.setdefault(league, []).append(parsed)

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

# Phase 1 repairs are not considered successful merely because a parser returned
# rows. Every repaired league must publish dates that are current as of the fixed
# Phase 1 reference date and inside both the 370-day publication horizon and that
# league's configured season window. This specifically catches stale-but-nonempty
# adapters such as a MotoGP feed returning old 2026 races.
if POLICY.exists():
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    season_windows = policy.get("leagueWindows") or {}
else:
    season_windows = {}

phase1 = root.get("phase1RepairReport") or {}
window_end = REFERENCE_DATE + timedelta(days=LOOKAHEAD_DAYS)

def in_season_window(dt, window):
    if not window or len(window) != 2:
        return True
    start_month, start_day = window[0]
    end_month, end_day = window[1]
    md = (dt.month, dt.day)
    start = (int(start_month), int(start_day))
    end = (int(end_month), int(end_day))
    return start <= md <= end if start <= end else (md >= start or md <= end)

for league in sorted(phase1):
    starts = parsed_starts.get(league) or []
    if not starts:
        raise SystemExit(f"REFRESH REJECTED: Phase 1 repaired {league} but final feed contains no events")

    season_window = season_windows.get(league)
    invalid = [dt for dt in starts if dt < REFERENCE_DATE or dt > window_end or not in_season_window(dt, season_window)]
    if invalid:
        minimum = min(starts).isoformat().replace("+00:00", "Z")
        maximum = max(starts).isoformat().replace("+00:00", "Z")
        bad_min = min(invalid).isoformat().replace("+00:00", "Z")
        bad_max = max(invalid).isoformat().replace("+00:00", "Z")
        policy_text = str(season_window) if season_window else "all-year/unspecified"
        raise SystemExit(
            f"REFRESH REJECTED: Phase 1 {league} date window invalid; "
            f"reference=2026-08-31T00:00:00Z horizon={window_end.isoformat().replace('+00:00','Z')} "
            f"season={policy_text} final_min={minimum} final_max={maximum} "
            f"invalid_min={bad_min} invalid_max={bad_max}"
        )

    print(
        f"Phase 1 date validation passed: {league}; "
        f"events={len(starts)}; min={min(starts).isoformat().replace('+00:00','Z')}; "
        f"max={max(starts).isoformat().replace('+00:00','Z')}"
    )

try:
    generated = datetime.fromisoformat(str(root.get("generatedAt")).replace("Z", "+00:00"))
    age_hours = (datetime.now(timezone.utc) - generated.astimezone(timezone.utc)).total_seconds() / 3600
    if age_hours > 30:
        raise SystemExit(f"REFRESH REJECTED: schedule feed is {age_hours:.1f}h old")
except SystemExit:
    raise
except Exception:
    raise SystemExit("REFRESH REJECTED: malformed generatedAt")

print(f"schedule refresh accepted: {len(events)} events, {len(counts)} leagues, {len(failed)} failed sources; no truncation detected; Phase 1 date windows valid")
