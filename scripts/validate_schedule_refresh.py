#!/usr/bin/env python3
"""Fail closed when a schedule refresh loses coverage, truncates leagues, or publishes no current Phase 1 coverage."""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

FEED = Path("data/schedule_feed.json")
POLICY = Path("data/schedule_season_policy.json")
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

# Phase 1 verification distinguishes legitimate historical rows from repaired/current
# coverage. Historical rows may remain for continuity; a repaired league must retain
# at least one event in the rolling current/future publication window.
if POLICY.exists():
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    season_windows = policy.get("leagueWindows") or {}
else:
    season_windows = {}

phase1 = root.get("phase1RepairReport") or {}

# Roll forward automatically on every refresh. Prefer the feed generation date because
# the feed is the artifact being validated; fall back to the runner's UTC date if the
# generation timestamp is unavailable or malformed.
def rolling_reference_date():
    try:
        generated = datetime.fromisoformat(str(root.get("generatedAt")).replace("Z", "+00:00"))
        return generated.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)

REFERENCE_DATE = rolling_reference_date()
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
    valid = [dt for dt in starts if REFERENCE_DATE <= dt <= window_end and in_season_window(dt, season_window)]
    stale_or_outside = [dt for dt in starts if dt < REFERENCE_DATE or dt > window_end or not in_season_window(dt, season_window)]

    if not valid:
        minimum = min(starts).isoformat().replace("+00:00", "Z")
        maximum = max(starts).isoformat().replace("+00:00", "Z")
        policy_text = str(season_window) if season_window else "all-year/unspecified"
        raise SystemExit(
            f"REFRESH REJECTED: Phase 1 {league} has no current/future coverage; "
            f"reference={REFERENCE_DATE.isoformat().replace('+00:00','Z')} horizon={window_end.isoformat().replace('+00:00','Z')} "
            f"season={policy_text} final_min={minimum} final_max={maximum} "
            f"stale_or_outside={len(stale_or_outside)}"
        )

    print(
        f"Phase 1 date validation passed: {league}; "
        f"reference={REFERENCE_DATE.isoformat().replace('+00:00','Z')}; "
        f"current_future={len(valid)}; stale_or_outside={len(stale_or_outside)}; "
        f"final_min={min(starts).isoformat().replace('+00:00','Z')}; "
        f"final_max={max(starts).isoformat().replace('+00:00','Z')}"
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

print(f"schedule refresh accepted: {len(events)} events, {len(counts)} leagues, {len(failed)} failed sources; no truncation detected; Phase 1 current/future coverage valid")
