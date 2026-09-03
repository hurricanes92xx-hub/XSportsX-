#!/usr/bin/env python3
"""Fail closed when a schedule refresh loses coverage, truncates leagues, or publishes no current coverage."""
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
if not events: raise SystemExit("REFRESH REJECTED: schedule feed has zero events")
if len(failed) >= 8 and len(events) < 100: raise SystemExit(f"REFRESH REJECTED: {len(failed)} sources failed and only {len(events)} events remain")

written_counts = {}; parsed_starts = {}
for event in events:
    league = event.get("league")
    if not league: raise SystemExit("REFRESH REJECTED: event without league")
    start = event.get("start")
    try: parsed = datetime.fromisoformat(str(start).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception: raise SystemExit(f"REFRESH REJECTED: malformed start timestamp for {league}: {start!r}")
    written_counts[league] = written_counts.get(league, 0) + 1
    parsed_starts.setdefault(league, []).append(parsed)

for league, expected in counts.items():
    actual = written_counts.get(league, 0)
    if actual != expected: raise SystemExit(f"REFRESH REJECTED: {league} count says {expected}, feed contains {actual}")
keys = [(e.get("league"), e.get("title"), e.get("start")) for e in events]
if len(keys) != len(set(keys)): raise SystemExit("REFRESH REJECTED: duplicate schedule events detected")
for league, minimum in (("NCAA Men's Soccer", 1), ("NCAA Women's Soccer", 1), ("NCAA Women's Volleyball", 1)):
    if league in counts and counts[league] < minimum: raise SystemExit(f"REFRESH REJECTED: {league} unexpectedly empty")

if POLICY.exists():
    policy = json.loads(POLICY.read_text(encoding="utf-8")); season_windows = policy.get("leagueWindows") or {}; next_season_coverage = policy.get("nextSeasonCoverage") or {}
else:
    season_windows = {}; next_season_coverage = {}

def rolling_reference_date():
    try: return datetime.fromisoformat(str(root.get("generatedAt")).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception: return datetime.now(timezone.utc)
REFERENCE_DATE = rolling_reference_date(); window_end = REFERENCE_DATE + timedelta(days=LOOKAHEAD_DAYS)

def in_season_window(dt, window):
    if not window or len(window) != 2: return True
    start_month, start_day = window[0]; end_month, end_day = window[1]; md = (dt.month, dt.day); start = (int(start_month), int(start_day)); end = (int(end_month), int(end_day))
    return start <= md <= end if start <= end else (md >= start or md <= end)

def in_next_season_window(dt, window):
    if not window or len(window) != 2 or dt.year != REFERENCE_DATE.year + 1: return False
    return in_season_window(dt, window)

# Hard guard for the current college-football season. The previous validator allowed
# a perfectly healthy-looking feed to publish with NCAA FB silently missing because
# football was not one of its required minimum leagues. During Aug-Jan, require a
# real FBS/FCS event inside the next three days so source drift fails closed.
if REFERENCE_DATE.month in (8, 9, 10, 11, 12, 1):
    football_starts = parsed_starts.get("NCAA FB", []) + parsed_starts.get("NCAA FCS", [])
    current_football = [dt for dt in football_starts if REFERENCE_DATE <= dt <= REFERENCE_DATE + timedelta(days=3)]
    if not current_football:
        raise SystemExit(
            "REFRESH REJECTED: NCAA football coverage missing from next 3 days; "
            f"reference={REFERENCE_DATE.isoformat().replace('+00:00','Z')} "
            "the feed cannot publish without NCAA FB/FCS current coverage"
        )
    print(f"NCAA football coverage guard passed: {len(current_football)} games in next 3 days")

phase1 = root.get("phase1RepairReport") or {}
for league in sorted(phase1):
    starts = parsed_starts.get(league) or []
    if not starts: raise SystemExit(f"REFRESH REJECTED: Phase 1 repaired {league} but final feed contains no events")
    season_window = season_windows.get(league); next_season_allowed = bool(next_season_coverage.get(league))
    valid = [dt for dt in starts if (REFERENCE_DATE <= dt <= window_end or (next_season_allowed and in_next_season_window(dt, season_window))) and in_season_window(dt, season_window)]
    stale_or_outside = [dt for dt in starts if not (REFERENCE_DATE <= dt <= window_end or (next_season_allowed and in_next_season_window(dt, season_window))) or not in_season_window(dt, season_window)]
    if not valid:
        minimum=min(starts).isoformat().replace("+00:00","Z"); maximum=max(starts).isoformat().replace("+00:00","Z"); policy_text=str(season_window) if season_window else "all-year/unspecified"
        raise SystemExit(f"REFRESH REJECTED: Phase 1 {league} has no current/future coverage; reference={REFERENCE_DATE.isoformat().replace('+00:00','Z')} horizon={window_end.isoformat().replace('+00:00','Z')} season={policy_text} next_season_allowed={next_season_allowed} final_min={minimum} final_max={maximum} stale_or_outside={len(stale_or_outside)}")
    print(f"Phase 1 date validation passed: {league}; reference={REFERENCE_DATE.isoformat().replace('+00:00','Z')}; current_future={len(valid)}; stale_or_outside={len(stale_or_outside)}; next_season_allowed={next_season_allowed}; final_min={min(starts).isoformat().replace('+00:00','Z')}; final_max={max(starts).isoformat().replace('+00:00','Z')}")

try:
    generated = datetime.fromisoformat(str(root.get("generatedAt")).replace("Z", "+00:00")); age_hours = (datetime.now(timezone.utc) - generated.astimezone(timezone.utc)).total_seconds() / 3600
    if age_hours > 30: raise SystemExit(f"REFRESH REJECTED: schedule feed is {age_hours:.1f}h old")
except SystemExit: raise
except Exception: raise SystemExit("REFRESH REJECTED: malformed generatedAt")
print(f"schedule refresh accepted: {len(events)} events, {len(counts)} leagues, {len(failed)} failed sources; no truncation detected; current NCAA football coverage verified")
