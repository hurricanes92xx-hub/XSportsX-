#!/usr/bin/env python3
"""NCAA schedule provider with dual-authority coverage.

The NCAA mirror is the primary authority, but it is not assumed to be complete.
ESPN is queried as a structured secondary authority for every NCAA league and
its records are unioned with the NCAA mirror. The canonical publisher performs
cross-provider identity merge, so this improves coverage without publishing
aliases twice.
"""
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

BASE = "https://ncaa-api.henrygd.me"
HEADERS = {"User-Agent": "XSportsX-Schedule/5.0", "Accept": "application/json"}
ESPN_HEADERS = {"User-Agent": "XSportsX-Schedule/5.0", "Accept": "application/json"}
NCAA_TZ = ZoneInfo("America/New_York")

NCAA_LEAGUES = [
    ("NCAA FB", "football", "fbs", "🏈"),
    ("NCAA BB", "basketball-men", "d1", "🏀"),
    ("NCAA WBB", "basketball-women", "d1", "🏀"),
    ("NCAA Baseball", "baseball", "d1", "⚾"),
    ("NCAA Softball", "softball", "d1", "🥎"),
    ("NCAA Men's Hockey", "icehockey-men", "d1", "🏒"),
    ("NCAA Women's Hockey", "icehockey-women", "d1", "🏒"),
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

ESPN_FALLBACK = {
    "NCAA FB": ("football", "college-football"),
    "NCAA BB": ("basketball", "mens-college-basketball"),
    "NCAA WBB": ("basketball", "womens-college-basketball"),
    "NCAA Baseball": ("baseball", "college-baseball"),
    "NCAA Softball": ("softball", "college-softball"),
    "NCAA Men's Hockey": ("hockey", "mens-college-hockey"),
    "NCAA Women's Hockey": ("hockey", "womens-college-hockey"),
    "NCAA Men's Soccer": ("soccer", "usa.ncaa.m.1"),
    "NCAA Women's Soccer": ("soccer", "usa.ncaa.w.1"),
    "NCAA Men's Lacrosse": ("lacrosse", "mens-college-lacrosse"),
    "NCAA Women's Lacrosse": ("lacrosse", "womens-college-lacrosse"),
    "NCAA Men's Volleyball": ("volleyball", "mens-college-volleyball"),
    "NCAA Women's Volleyball": ("volleyball", "womens-college-volleyball"),
    "NCAA Men's Water Polo": ("water-polo", "mens-college-water-polo"),
    "NCAA Women's Water Polo": ("water-polo", "womens-college-water-polo"),
    "NCAA Women's Field Hockey": ("field-hockey", "womens-college-field-hockey"),
    "NCAA Beach Volleyball": ("beach-volleyball", "ncaa-beach-volleyball"),
}


def _get(url, headers=HEADERS, timeout=15):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read())


def _parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _walk_games(value):
    if isinstance(value, dict):
        if (value.get("startDate") or value.get("gameDate") or value.get("date")) and (
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
    if isinstance(game.get("status"), dict):
        state = str(game["status"].get("state") or game["status"].get("name") or "").lower()
    tag = "LIVE" if state in {"live", "in-progress", "in", "in progress", "in_progress"} else "FINAL" if state in {"final", "f", "complete", "completed", "closed"} else "UPCOMING"
    provider_id = game.get("contestId") or game.get("gameID") or game.get("gameId") or ""
    event = {"league": league, "title": title, "start": start, "tag": tag, "icon": icon, "source": "ncaa"}
    if away:
        event["away"] = away
    if home:
        event["home"] = home
    if provider_id:
        event["providerEventId"] = f"ncaa:{provider_id}"
    return event


def _normalize_espn(game, league, icon):
    dt = _parse_iso(game.get("date"))
    if not dt:
        return None
    comp = (game.get("competitions") or [{}])[0]
    competitors = comp.get("competitors") or []
    home = next((x.get("team", {}).get("shortDisplayName") or x.get("team", {}).get("displayName") for x in competitors if x.get("homeAway") == "home"), "")
    away = next((x.get("team", {}).get("shortDisplayName") or x.get("team", {}).get("displayName") for x in competitors if x.get("homeAway") == "away"), "")
    title = f"{away} @ {home}" if away and home else str(game.get("name") or game.get("shortName") or league)
    state = str(((comp.get("status") or {}).get("type") or {}).get("state") or "").lower()
    tag = "LIVE" if state == "in" else "FINAL" if state == "post" else "UPCOMING"
    event = {"league": league, "title": title, "start": dt.isoformat().replace("+00:00", "Z"), "tag": tag, "icon": icon, "source": "espn-ncaa-fallback"}
    if away:
        event["away"] = away
    if home:
        event["home"] = home
    if game.get("id"):
        event["providerEventId"] = f"espn:{game['id']}"
    return event


def _fetch_scoreboard_day(sport, division, day):
    if sport == "football":
        url = f"{BASE}/scoreboard/football/{division}"
    else:
        url = f"{BASE}/scoreboard/{sport}/{division}/{day:%Y/%m/%d}"
    try:
        return _get(url)
    except Exception as exc:
        print(f"ERROR NCAA scoreboard {sport}/{division} {day}: {exc}")
        return None


def _fetch_espn_day(league, day):
    mapping = ESPN_FALLBACK.get(league)
    if not mapping:
        return []
    sport, slug = mapping
    url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/scoreboard?dates={day:%Y%m%d}&limit=1000"
    try:
        root = _get(url, ESPN_HEADERS, timeout=20)
    except Exception as exc:
        print(f"ERROR ESPN NCAA secondary {league} {day}: {exc}")
        return []
    icon = next(x[3] for x in NCAA_LEAGUES if x[0] == league)
    return [event for game in (root.get("events") or []) if (event := _normalize_espn(game, league, icon))]


def _fetch_espn_days(league, days):
    out = []
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(days)))) as pool:
        futures = [pool.submit(_fetch_espn_day, league, day) for day in days]
        for future in as_completed(futures):
            out.extend(future.result())
    return out


def _fetch_primary_days(sport, division, days):
    if sport == "football":
        return [_fetch_scoreboard_day(sport, division, days[0])]
    roots = []
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(days)))) as pool:
        futures = [pool.submit(_fetch_scoreboard_day, sport, division, day) for day in days]
        for future in as_completed(futures):
            roots.append(future.result())
    return roots


def _in_window(event, now, cutoff):
    dt = _parse_iso(event.get("start"))
    return bool(dt and now - timedelta(hours=12) <= dt <= cutoff)


def fetch_league(league, sport, division, icon, horizon_days=30):
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=min(horizon_days, 7))
    days = [now.date() + timedelta(days=i) for i in range((cutoff.date() - now.date()).days + 1)]
    primary = []

    # Primary NCAA mirror.
    for root in _fetch_primary_days(sport, division, days):
        if not root:
            continue
        for game in _walk_games(root):
            event = _normalize(game, league, icon)
            if event and _in_window(event, now, cutoff):
                primary.append(event)

    # Always query the structured secondary authority. The old implementation
    # queried ESPN only when the NCAA feed returned zero rows, which silently
    # dropped live matches whenever the primary feed was merely incomplete.
    secondary = [e for e in _fetch_espn_days(league, days) if _in_window(e, now, cutoff)]

    # Deduplicate within the provider using structured provider IDs when present,
    # otherwise exact matchup/start. Cross-provider merging is done centrally by
    # refresh_schedules.py, where source priority and broader identity matching live.
    out = []
    seen = set()
    for event in primary + secondary:
        key = event.get("providerEventId") or (event.get("league"), event.get("away"), event.get("home"), event.get("start"))
        if key in seen:
            continue
        seen.add(key)
        out.append(event)

    if secondary and not primary:
        print(f"REPAIRED NCAA {league} via ESPN secondary: {len(secondary)} events")
    elif secondary:
        print(f"NCAA {league}: primary={len(primary)} secondary={len(secondary)} union={len(out)}")
    return out
