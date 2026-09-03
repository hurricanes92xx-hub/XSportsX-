#!/usr/bin/env python3
"""TheSportsDB schedule provider for leagues without a healthy primary API."""
import json
import urllib.request
from datetime import datetime, timezone

BASE_V1 = "https://www.thesportsdb.com/api/v1/json/123"

# Only use this adapter for leagues where it is a deliberate alternate source.
LEAGUE_MAP = {
    "EPL": 4328, "LaLiga": 4335, "Serie A": 4332, "Bundesliga": 4331,
    "Ligue 1": 4334, "MLS": 4346, "NBA": 4387, "NHL": 4380,
    "NFL": 4391, "MLB": 4424, "UFC": 4442,
    "ATP": 4464,
    "IPL": 4460,
    "ICC T20": 5103,
    "FIVB Men": 5083,
    "FIVB Women": 5084,
}
SPORTDB_LEAGUES = set(LEAGUE_MAP)


def _request(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "XSportsX-Schedule/4.0", "Accept": "application/json"})
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
    if not start and item.get("dateEvent"):
        start = _parse_time(f"{item['dateEvent']}T{item.get('strTime') or '00:00:00'}Z")
    if not title or not start:
        return None
    status = str(item.get("strStatus") or "").lower()
    if status in {"match finished", "finished", "ft"}:
        tag = "FINAL"
    elif status in {"live", "in progress", "1h", "2h", "ht"}:
        tag = "LIVE"
    else:
        tag = "UPCOMING"
    event = {
        "league": league, "title": title, "start": start, "tag": tag,
        "icon": "🏆", "source": "sportsdb",
        "sportsDbEventId": str(item.get("idEvent") or ""),
        "sportsDbHomeTeamId": str(item.get("idHomeTeam") or ""),
        "sportsDbAwayTeamId": str(item.get("idAwayTeam") or ""),
    }
    if home: event["home"] = home
    if away: event["away"] = away
    if item.get("strThumb"): event["artUrl"] = str(item["strThumb"])
    return event


def fetch_league(league, season=None):
    if league not in SPORTDB_LEAGUES:
        return []
    try:
        league_id = LEAGUE_MAP[league]
        root = json.loads(_request(f"{BASE_V1}/eventsnextleague.php?id={league_id}"))
        return [event for event in (_normalize_event(x, league) for x in (root.get("events") or [])) if event]
    except Exception as exc:
        print(f"ERROR SportsDB alternate {league}: {exc}")
        return []


def current_season():
    now = datetime.now(timezone.utc)
    return f"{now.year}-{now.year + 1}" if now.month >= 7 else f"{now.year - 1}-{now.year}"
