#!/usr/bin/env python3
"""NCAA schedule provider.

Uses the free henrygd/ncaa-api schedule route as a machine-readable NCAA
source. The provider is deliberately month-based: one request covers a
calendar month instead of hammering the public API once per day.
"""
import json
import urllib.request
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

BASE = "https://ncaa-api.henrygd.me"
HEADERS = {"User-Agent": "XSportsX-Schedule/3.0", "Accept": "application/json"}
NCAA_TZ = ZoneInfo("America/New_York")

NCAA_LEAGUES = [
    ("NCAA FB", "football", "fbs", "🏈"),
    ("NCAA BB", "basketball-men", "d1", "🏀"),
    ("NCAA WBB", "basketball-women", "d1", "🏀"),
    ("NCAA Baseball", "baseball", "d1", "⚾"),
    ("NCAA Softball", "softball", "d1", "🥎"),
    ("NCAA Men's Hockey", "icehockey-men", "d1", "🏒"),
    ("NCAA Men's Soccer", "soccer-men", "d1", "⚽"),
    ("NCAA Women's Soccer", "soccer-women", "d1", "⚽"),
    ("NCAA Men's Lacrosse", "lacrosse-men", "d1", "🥍"),
    ("NCAA Women's Lacrosse", "lacrosse-women", "d1", "🥍"),
    ("NCAA Men's Volleyball", "volleyball-men", "d1", "🏐"),
    ("NCAA Women's Volleyball", "volleyball-women", "d1", "🏐"),
    ("NCAA Men's Water Polo", "waterpolo-men", "d1", "🤽"),
    ("NCAA Women's Water Polo", "waterpolo-women", "d1", "🤽"),
    ("NCAA Women's Field Hockey", "fieldhockey-women", "d1", "🏑"),
    ("NCAA Beach Volleyball", "beach-volleyball", "d1", "🏐"),
]


def _get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read())


def _month_keys(now=None):
    now = now or datetime.now(timezone.utc)
    keys = []
    for offset in (0, 1):
        month = now.month - 1 + offset
        year = now.year + month // 12
        month = month % 12 + 1
        keys.append((year, month))
    return keys


def _walk_games(value):
    if isinstance(value, dict):
        if (value.get("startDate") or value.get("gameDate")) and (
            value.get("away") or value.get("home") or value.get("teams") or value.get("contestId") or value.get("gameID")
        ):
            yield value
        for child in value.values():
            yield from _walk_games(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_games(child)


def _team_name(team):
    if not isinstance(team, dict):
        return ""
    names = team.get("names") or {}
    return str(names.get("short") or names.get("full") or names.get("seo") or team.get("name") or "").strip()


def _parse_time(game):
    date = str(game.get("startDate") or game.get("gameDate") or "").strip()
    if not date:
        return None
    raw = str(game.get("startTime") or "").strip().upper().replace(" ET", "")
    if not raw:
        return f"{date}T00:00:00Z"
    for fmt in ("%Y-%m-%d %I:%M%p", "%Y-%m-%d %H:%M", "%Y-%m-%dT%I:%M%p", "%Y-%m-%dT%H:%M"):
        try:
            text = f"{date} {raw}" if "T" not in date else f"{date}T{raw}"
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=NCAA_TZ).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            continue
    return f"{date}T00:00:00Z"


def _normalize(game, league, icon):
    away = _team_name(game.get("away"))
    home = _team_name(game.get("home"))
    teams = game.get("teams") or []
    if not away and isinstance(teams, list) and teams:
        away = _team_name(teams[0])
    if not home and isinstance(teams, list) and len(teams) > 1:
        home = _team_name(teams[1])
    title = f"{away} @ {home}" if away and home else str(game.get("title") or game.get("contestName") or league)
    start = _parse_time(game)
    if not start:
        return None
    state = str(game.get("gameState") or game.get("status") or "").lower()
    tag = "LIVE" if state in {"live", "in-progress", "in", "in progress"} else "FINAL" if state in {"final", "f", "complete", "completed"} else "UPCOMING"
    provider_id = game.get("contestId") or game.get("gameID") or game.get("gameId") or ""
    event = {"league": league, "title": title, "start": start, "tag": tag, "icon": icon, "source": "ncaa"}
    if provider_id:
        event["providerEventId"] = f"ncaa:{provider_id}"
    return event


def fetch_league(league, sport, division, icon, horizon_days=30):
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=horizon_days)
    events = []
    seen = set()
    for year, month in _month_keys(now):
        month_arg = "" if sport == "football" else f"/{month:02d}"
        url = f"{BASE}/schedule/{sport}/{division}/{year}{month_arg}"
        try:
            root = _get(url)
        except Exception as exc:
            print(f"ERROR NCAA {league} {year}-{month:02d}: {exc}")
            continue
        for game in _walk_games(root):
            event = _normalize(game, league, icon)
            if not event:
                continue
            dt = datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
            if dt < now - timedelta(hours=12) or dt > cutoff:
                continue
            key = (event["title"], event["start"])
            if key in seen:
                continue
            seen.add(key)
            events.append(event)
    return events
