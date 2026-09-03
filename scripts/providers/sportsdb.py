#!/usr/bin/env python3
"""TheSportsDB schedule adapter.

Designed as a low-pressure secondary schedule authority. Premium V2 is preferred
because it can return an entire league season in one request; V1 is supported for
backend development when a key is supplied. The caller owns caching/fallback policy.
"""
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

BASE_V1 = "https://www.thesportsdb.com/api/v1/json"
BASE_V2 = "https://www.thesportsdb.com/api/v2/json"
KEY = os.getenv("SPORTSDB_API_KEY", "").strip()

LEAGUE_MAP = {
    "EPL": 4328,
    "LaLiga": 4335,
    "Serie A": 4332,
    "Bundesliga": 4331,
    "Ligue 1": 4334,
    "MLS": 4346,
    "NBA": 4387,
    "NHL": 4380,
    "NFL": 4391,
    "MLB": 4424,
    "UFC": 4442,
}

SPORTDB_LEAGUES = set(LEAGUE_MAP)


def _request(url, headers=None, timeout=12):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "XSportsX-Schedule/2.1",
            "Accept": "application/json",
            **(headers or {}),
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def _parse_time(value):
    if not value:
        return None
    text = str(value).strip()
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            pass
    return None


def _normalize_event(item, league):
    if not isinstance(item, dict):
        return None
    home = str(item.get("strHomeTeam") or "").strip()
    away = str(item.get("strAwayTeam") or "").strip()
    title = str(item.get("strEvent") or "").strip()
    if not title and home and away:
        title = f"{away} @ {home}"
    start = _parse_time(item.get("strTimestamp"))
    if not start:
        date = item.get("dateEvent")
        time = item.get("strTime")
        if date:
            start = _parse_time(f"{date}T{time or '00:00:00'}Z")
    if not title or not start:
        return None
    status = str(item.get("strStatus") or "").lower()
    tag = "FINAL" if status in {"match finished", "finished", "ft"} else "LIVE" if status in {"live", "in progress", "1h", "2h", "ht"} else "UPCOMING"
    return {
        "league": league,
        "title": title,
        "start": start,
        "tag": tag,
        "icon": "🏆",
        "source": "sportsdb",
        "sportsDbEventId": str(item.get("idEvent") or ""),
        "sportsDbHomeTeamId": str(item.get("idHomeTeam") or ""),
        "sportsDbAwayTeamId": str(item.get("idAwayTeam") or ""),
    }


def fetch_league(league, season=None):
    """Return normalized events or [] without raising provider errors."""
    if not KEY or league not in SPORTDB_LEAGUES:
        return []
    league_id = LEAGUE_MAP[league]
    try:
        if season:
            path = f"/schedule/league/{league_id}/{urllib.parse.quote(str(season), safe='-') }"
            raw = _request(BASE_V2 + path, {"X-API-KEY": KEY})
            root = json.loads(raw)
            items = root.get("events") or root.get("data") or []
        else:
            # V1 next-league is intentionally only a safety fallback. It has a
            # small free-key result cap, so it must never be used as a bulk source.
            url = f"{BASE_V1}/{urllib.parse.quote(KEY, safe='')}/eventsnextleague.php?id={league_id}"
            root = json.loads(_request(url))
            items = root.get("events") or []
        return [event for event in (_normalize_event(x, league) for x in items) if event]
    except Exception as exc:
        print(f"ERROR SportsDB {league}: {exc}")
        return []


def current_season():
    now = datetime.now(timezone.utc)
    return f"{now.year}-{now.year + 1}" if now.month >= 7 else f"{now.year - 1}-{now.year}"
