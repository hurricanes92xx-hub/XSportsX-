#!/usr/bin/env python3
"""Keyless/free sports providers used as secondary evidence.

These adapters never provide playback URLs. They only contribute schedule/live
metadata to the canonical merge layer. Credentials are not persisted.
"""
from __future__ import annotations
import json, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

HEADERS = {"User-Agent": "XSportsX-Schedule/1.0", "Accept": "application/json"}


def _get(url, timeout=10):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def _iso(value):
    if not value:
        return ""
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return str(value)


def _norm(value):
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _status(value):
    s = str(value or "").lower().replace("-", "_").replace(" ", "_")
    if s in {"live", "in", "in_progress", "inprogress", "playing", "1h", "2h", "ht"}:
        return "LIVE"
    if s in {"final", "finished", "complete", "completed", "post", "ended"}:
        return "FINAL"
    return "UPCOMING"


def sportscore(league, icon):
    """Use SportScore only as a live/recent shadow source.

    Its documented free widget endpoint is limited to football, basketball,
    cricket and tennis and returns a competition field. We only retain rows
    whose competition maps to the requested canonical league, preventing a
    broad feed from polluting unrelated league buckets.
    """
    sport_by_league = {
        "EPL": "football", "UCL": "football", "UEL": "football", "LaLiga": "football",
        "Serie A": "football", "Bundesliga": "football", "Ligue 1": "football", "MLS": "football",
        "NWSL": "football", "NBA": "basketball", "WNBA": "basketball", "IPL": "cricket",
        "ICC T20": "cricket", "ATP": "tennis", "WTA": "tennis",
    }
    sport = sport_by_league.get(league)
    if not sport:
        return True, [], "unsupported league for SportScore"
    url = "https://sportscore.com/api/widget/matches/?" + urllib.parse.urlencode({"sport": sport, "limit": 50, "src": "XSportsX"})
    try:
        root = _get(url, timeout=8)
        rows = root.get("matches") if isinstance(root, dict) else root
        out = []
        for item in rows or []:
            if not isinstance(item, dict):
                continue
            competition = item.get("competition") or item.get("league") or ""
            if _norm(competition) != _norm(league) and not _competition_matches(competition, league):
                continue
            home = str(item.get("home") or item.get("home_team") or "").strip()
            away = str(item.get("away") or item.get("away_team") or "").strip()
            start = _iso(item.get("time") or item.get("start") or item.get("date"))
            if not home or not away or not start:
                continue
            out.append({"league": league, "title": f"{away} @ {home}", "start": start,
                        "tag": _status(item.get("status")), "icon": icon, "source": "sportscore",
                        "home": home, "away": away,
                        "providerEventId": f"sportscore:{item.get('id') or _norm(away)+'-'+_norm(home)+'-'+start}",
                        "attribution": "SportScore"})
        return True, out, ""
    except Exception as exc:
        return False, [], f"{type(exc).__name__}: {exc}"


def _competition_matches(value, league):
    aliases = {
        "EPL": {"englishpremierleague", "premierleague"},
        "UCL": {"uefachampionsleague", "championsleague"},
        "UEL": {"uefaeuropaleague", "europaleague"},
        "LaLiga": {"laliga", "spanishlaliga"},
        "Serie A": {"seriea", "italianseriea"},
        "Bundesliga": {"bundesliga", "germanbundesliga"},
        "Ligue 1": {"ligue1", "frenchligue1"},
        "MLS": {"mls", "majorleaguesoccer"},
        "NWSL": {"nwsl", "nationalwomenssoccerleague"},
        "NBA": {"nba", "nationalbasketballassociation"},
        "WNBA": {"wnba", "womensnationalbasketballassociation"},
        "IPL": {"ipl", "indianpremierleague"},
        "ICC T20": {"icct20", "t20worldcup", "internationalcrickett20"},
        "ATP": {"atp", "atptour"},
        "WTA": {"wta", "wtatour"},
    }
    return _norm(value) in aliases.get(league, set())


def jolpica_f1(league, icon):
    if league != "F1":
        return True, [], "unsupported league for Jolpica"
    year = datetime.now(timezone.utc).year
    try:
        root = _get(f"https://api.jolpi.ca/ergast/f1/{year}.json", timeout=8)
        races = (((root.get("MRData") or {}).get("RaceTable") or {}).get("Races") or [])
        out = []
        for race in races:
            race_name = race.get("raceName") or race.get("Circuit", {}).get("circuitName") or "Formula 1"
            date = race.get("date"); time = race.get("time") or "00:00:00Z"
            if not date:
                continue
            out.append({"league": "F1", "title": race_name, "start": _iso(f"{date}T{time}"),
                        "tag": "UPCOMING", "icon": icon, "source": "jolpica-f1",
                        "providerEventId": f"jolpica:{race.get('round') or race_name}"})
        return True, out, ""
    except Exception as exc:
        return False, [], f"{type(exc).__name__}: {exc}"


def openf1(league, icon):
    if league != "F1":
        return True, [], "unsupported league for OpenF1"
    try:
        root = _get("https://api.openf1.org/v1/sessions?session_key=latest", timeout=8)
        rows = root if isinstance(root, list) else []
        out = []
        for item in rows:
            start = _iso(item.get("date_start") or item.get("date_end"))
            name = item.get("session_name") or item.get("meeting_name") or "Formula 1"
            if not start:
                continue
            out.append({"league": "F1", "title": name, "start": start,
                        "tag": "LIVE" if item.get("session_key") else "UPCOMING", "icon": icon,
                        "source": "openf1", "providerEventId": f"openf1:{item.get('session_key') or start}"})
        return True, out, ""
    except Exception as exc:
        return False, [], f"{type(exc).__name__}: {exc}"


def openliga(league, icon):
    if league != "Bundesliga":
        return True, [], "unsupported league for OpenLigaDB"
    try:
        year = datetime.now(timezone.utc).year
        root = _get(f"https://api.openligadb.de/getmatchdata/bl1/{year}", timeout=8)
        out = []
        for item in root if isinstance(root, list) else []:
            h = ((item.get("team1") or {}).get("teamName") or "").strip()
            a = ((item.get("team2") or {}).get("teamName") or "").strip()
            start = _iso(item.get("matchDateTimeUTC") or item.get("matchDateTime"))
            if not h or not a or not start:
                continue
            out.append({"league": "Bundesliga", "title": f"{a} @ {h}", "start": start,
                        "tag": "FINAL" if item.get("matchIsFinished") else "UPCOMING", "icon": icon,
                        "source": "openligadb", "home": h, "away": a,
                        "providerEventId": f"openligadb:{item.get('matchID') or start}"})
        return True, out, ""
    except Exception as exc:
        return False, [], f"{type(exc).__name__}: {exc}"


def fetch(provider, league, icon):
    if provider == "sportscore":
        return sportscore(league, icon)
    if provider == "jolpica-f1":
        return jolpica_f1(league, icon)
    if provider == "openf1":
        return openf1(league, icon)
    if provider == "openligadb":
        return openliga(league, icon)
    return False, [], "unknown free provider"
