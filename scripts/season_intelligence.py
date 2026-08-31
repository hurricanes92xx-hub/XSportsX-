#!/usr/bin/env python3
"""Deterministic season/activity intelligence for the XSportsX scheduler.

It combines configured season windows with observed canonical-feed activity.
Official sources are still queried every refresh so a newly announced season can
wake a league up; provider/NCAA fallbacks can be skipped during quiet periods.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "data" / "schedule_season_policy.json"


def _load_policy() -> dict:
    try:
        return json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"default": {"unknownLeagueMode": "active", "inactiveProbeHours": 24, "recentActivityDays": 45}, "leagueWindows": {}}


def _window_active(today: date, windows: list[list[int]]) -> bool:
    if not windows:
        return True
    md = today.month * 100 + today.day
    for start, end in windows:
        start_md, end_md = int(start[0]) * 100 + int(start[1]), int(end[0]) * 100 + int(end[1])
        if start_md <= end_md:
            if start_md <= md <= end_md:
                return True
        elif md >= start_md or md <= end_md:
            return True
    return False


def _parse_event_time(value: str):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def analyze(league: str, previous_events: list[dict] | None = None, now: datetime | None = None) -> dict:
    policy = _load_policy()
    default = policy.get("default", {})
    windows = policy.get("leagueWindows", {}).get(league)
    now = now or datetime.now(timezone.utc)
    today = now.date()
    observed = []
    for event in previous_events or []:
        if event.get("league") != league:
            continue
        dt = _parse_event_time(event.get("start") or event.get("startUtc"))
        if dt:
            observed.append(dt)
    lookahead = now + timedelta(days=370)
    recent_cutoff = now - timedelta(days=int(default.get("recentActivityDays", 45)))
    upcoming = [dt for dt in observed if now - timedelta(hours=12) <= dt <= lookahead]
    recent = [dt for dt in observed if recent_cutoff <= dt <= now + timedelta(days=1)]
    configured_active = _window_active(today, windows) if windows else None
    # Observed upcoming/recent events override a conservative calendar window.
    observed_active = bool(upcoming or recent)
    active = observed_active or configured_active is True or (configured_active is None and default.get("unknownLeagueMode") == "active")
    if active:
        refresh_class = "active"
        probe_hours = int(default.get("activeProbeHours", 1))
        reason = "observed_activity" if observed_active else "season_window"
    else:
        refresh_class = "inactive"
        probe_hours = int(default.get("inactiveProbeHours", 24))
        reason = "outside_season_window"
    return {
        "league": league,
        "active": active,
        "class": refresh_class,
        "probeHours": probe_hours,
        "reason": reason,
        "configuredSeason": windows or [],
        "observedUpcoming": len(upcoming),
        "observedRecent": len(recent),
    }


def should_refresh_provider(league: str, previous_events: list[dict] | None = None, now: datetime | None = None) -> bool:
    return bool(analyze(league, previous_events, now)["active"])


def report(leagues: list[str], previous_events: list[dict] | None = None) -> list[dict]:
    return [analyze(league, previous_events) for league in leagues]
