#!/usr/bin/env python3
"""Canonical cross-provider event identity and metadata merge helpers."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

# High-confidence aliases for providers that publish city-only or alternate names.
# Keep this deliberately conservative: aliases are used only inside the same canonical league.
TEAM_ALIASES = {
    "mlb": {
        "toronto": "blue jays", "toronto blue jays": "blue jays",
        "cleveland": "guardians", "cleveland guardians": "guardians",
        "san francisco": "giants", "san francisco giants": "giants",
        "pittsburgh": "pirates", "pittsburgh pirates": "pirates",
        "new york yankees": "yankees", "ny yankees": "yankees",
        "new york mets": "mets", "ny mets": "mets",
        "boston red sox": "red sox", "tampa bay rays": "rays",
        "baltimore orioles": "orioles", "detroit tigers": "tigers",
        "chicago white sox": "white sox", "chicago cubs": "cubs",
        "kansas city royals": "royals", "minnesota twins": "twins",
        "houston astros": "astros", "texas rangers": "rangers",
        "seattle mariners": "mariners", "oakland athletics": "athletics",
        "los angeles angels": "angels", "los angeles dodgers": "dodgers",
        "san diego padres": "padres", "arizona diamondbacks": "diamondbacks",
        "colorado rockies": "rockies", "atlanta braves": "braves",
        "miami marlins": "marlins", "milwaukee brewers": "brewers",
        "cincinnati reds": "reds", "st louis cardinals": "cardinals",
        "washington nationals": "nationals", "philadelphia phillies": "phillies",
    }
}

LEAGUE_ALIASES = {
    "ncaafb": "ncaa fb", "ncaa fbs": "ncaa fb", "ncaa football": "ncaa fb",
    "ncaa mens hockey": "ncaa men's hockey", "ncaa womens hockey": "ncaa women's hockey",
    "ncaabb": "ncaa bb", "ncaa mens basketball": "ncaa bb", "ncaa womens basketball": "ncaa wbb",
}

SPORT_BY_LEAGUE = {
    "mlb": "baseball", "nba": "basketball", "wnba": "basketball", "nfl": "football", "nhl": "hockey",
    "mls": "soccer", "epl": "soccer", "ucl": "soccer", "laliga": "soccer", "serie a": "soccer",
    "bundesliga": "soccer", "ligue 1": "soccer", "ufc": "mma", "f1": "racing", "indycar": "racing",
    "pga": "golf", "lpga": "golf", "liv golf": "golf", "atp": "tennis", "wta": "tennis",
    "pll": "lacrosse", "nll": "lacrosse", "nrl": "rugby-league", "afl": "australian-football",
    "ncaa fb": "football", "ncaa fcs": "football", "ncaa bb": "basketball", "ncaa wbb": "basketball",
    "ncaa baseball": "baseball", "ncaa softball": "softball", "ncaa men's hockey": "hockey", "ncaa women's hockey": "hockey",
    "ncaa men's soccer": "soccer", "ncaa women's soccer": "soccer", "ncaa men's lacrosse": "lacrosse", "ncaa women's lacrosse": "lacrosse",
    "ncaa men's volleyball": "volleyball", "ncaa women's volleyball": "volleyball", "ncaa men's water polo": "water-polo",
    "ncaa women's water polo": "water-polo", "ncaa women's field hockey": "field-hockey", "ncaa beach volleyball": "beach-volleyball",
}

TOLERANCE_MINUTES = {
    "baseball": 150, "basketball": 120, "football": 180, "hockey": 150, "soccer": 150,
    "tennis": 360, "golf": 720, "racing": 180, "mma": 360, "lacrosse": 150,
    "volleyball": 180, "rugby": 180, "rugby-league": 180, "cricket": 180, "australian-football": 180,
    "softball": 180, "water-polo": 180, "field-hockey": 180, "beach-volleyball": 180,
}


def normalize_text(value: object) -> str:
    text = str(value or "").lower().replace("&", " and ")
    text = re.sub(r"\b(at|vs\.?|versus)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def normalize_league(value: object) -> str:
    text = normalize_text(value)
    compact = text.replace(" ", "")
    return LEAGUE_ALIASES.get(compact, text)


def normalize_start(value: object) -> str:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except Exception:
        return ""


def _team(value: object, league: str) -> str:
    text = normalize_text(value)
    aliases = TEAM_ALIASES.get(league, {})
    if text in aliases:
        return aliases[text]
    # Provider-specific structured names often include the canonical team name.
    # A direct alias is safer than fuzzy matching across leagues.
    for alias, canonical in aliases.items():
        if text == alias or (len(alias) > 5 and alias in text):
            return canonical
    return text


def _extract_teams(event: dict, league: str) -> tuple[str, str]:
    home = event.get("home") or event.get("homeTeam") or ""
    away = event.get("away") or event.get("awayTeam") or ""
    if home or away:
        return _team(home, league), _team(away, league)
    title = normalize_text(event.get("title"))
    parts = re.split(r"\s+at\s+|\s+vs\s+|\s+versus\s+|\s+@\s+", title)
    if len(parts) == 2:
        return _team(parts[1], league), _team(parts[0], league)
    return "", ""


def _provider_ids(event: dict) -> set[str]:
    ids = set()
    for key in ("providerEventId", "espnEventId", "sportsDbEventId", "eventId"):
        value = str(event.get(key) or "").strip()
        if value:
            ids.add(value.lower())
    return ids


def canonical_event_key(event: dict) -> tuple:
    """Return a conservative identity tuple.

    Team events use canonical home/away names plus a sport-aware start bucket.
    Non-team events use normalized title plus the same time bucket.
    """
    league = normalize_league(event.get("league"))
    sport = SPORT_BY_LEAGUE.get(league, normalize_text(event.get("sport")))
    start = normalize_start(event.get("start") or event.get("startUtc"))
    if not start:
        bucket = ""
    else:
        dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        tolerance = TOLERANCE_MINUTES.get(sport, 180)
        # 30-minute base buckets; matching later uses absolute tolerance.
        bucket = int(dt.timestamp() // (30 * 60))
    home, away = _extract_teams(event, league)
    if home and away:
        return (sport, league, home, away, bucket)
    return (sport, league, normalize_text(event.get("title")), bucket)


def provider_identity(provider: object, provider_event_id: object) -> str:
    provider = normalize_text(provider)
    provider_event_id = str(provider_event_id or "").strip()
    if not provider or not provider_event_id:
        return ""
    return f"{provider}:{provider_event_id}"


def event_identity(league: object, title: object, start: object) -> str:
    canonical = "|".join((normalize_league(league), normalize_text(title), normalize_start(start)))
    return "evt_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def identity_match(a: dict, b: dict) -> bool:
    """Match two provider records without relying on title equality."""
    la, lb = normalize_league(a.get("league")), normalize_league(b.get("league"))
    if not la or la != lb:
        return False
    if _provider_ids(a) & _provider_ids(b):
        return True
    ha, aa = _extract_teams(a, la)
    hb, ab = _extract_teams(b, lb)
    sa, sb = normalize_start(a.get("start") or a.get("startUtc")), normalize_start(b.get("start") or b.get("startUtc"))
    if not sa or not sb:
        return False
    ta = datetime.fromisoformat(sa.replace("Z", "+00:00"))
    tb = datetime.fromisoformat(sb.replace("Z", "+00:00"))
    sport = SPORT_BY_LEAGUE.get(la, normalize_text(a.get("sport")))
    tolerance = TOLERANCE_MINUTES.get(sport, 180)
    if abs((ta - tb).total_seconds()) > tolerance * 60:
        return False
    if ha and aa and hb and ab:
        return ha == hb and aa == ab
    if ha or aa or hb or ab:
        return False
    return normalize_text(a.get("title")) == normalize_text(b.get("title"))


def merge_event_records(winner: dict, candidate: dict) -> dict:
    """Keep authoritative identity/status while filling missing metadata."""
    out = dict(winner)
    for key, value in candidate.items():
        if key in {"source", "tag"}:
            continue
        if value not in (None, "", [], {}):
            if out.get(key) in (None, "", [], {}):
                out[key] = value
    # Prefer structured team fields over title-only records.
    for key in ("home", "away", "homeTeamId", "awayTeamId", "homeLogo", "awayLogo", "broadcast", "sourceUrl", "youtubeVideoId"):
        if candidate.get(key) and not out.get(key):
            out[key] = candidate[key]
    return out
