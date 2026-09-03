#!/usr/bin/env python3
"""Canonical cross-provider event identity and metadata merge helpers.

The event is the unit of truth. Provider records are observations attached to
that event; they are never allowed to create a second event merely because a
team/league label differs.
"""
from __future__ import annotations
import hashlib
import re
from datetime import datetime, timezone

TEAM_ALIASES = {
    "mlb": {
        "toronto": "blue jays", "toronto blue jays": "blue jays", "cleveland": "guardians", "cleveland guardians": "guardians",
        "san francisco": "giants", "san francisco giants": "giants", "pittsburgh": "pirates", "pittsburgh pirates": "pirates",
        "new york yankees": "yankees", "ny yankees": "yankees", "new york mets": "mets", "ny mets": "mets",
        "boston red sox": "red sox", "tampa bay rays": "rays", "baltimore orioles": "orioles", "detroit tigers": "tigers",
        "chicago white sox": "white sox", "chicago cubs": "cubs", "kansas city royals": "royals", "minnesota twins": "twins",
        "houston astros": "astros", "texas rangers": "rangers", "seattle mariners": "mariners", "oakland athletics": "athletics",
        "los angeles angels": "angels", "los angeles dodgers": "dodgers", "san diego padres": "padres", "arizona diamondbacks": "diamondbacks",
        "colorado rockies": "rockies", "atlanta braves": "braves", "miami marlins": "marlins", "milwaukee brewers": "brewers",
        "cincinnati reds": "reds", "st louis cardinals": "cardinals", "washington nationals": "nationals", "philadelphia phillies": "phillies",
    },
    "nfl": {
        "new england": "patriots", "new england patriots": "patriots", "buffalo": "bills", "buffalo bills": "bills",
        "miami": "dolphins", "miami dolphins": "dolphins", "new york giants": "giants", "ny giants": "giants",
        "new york jets": "jets", "ny jets": "jets", "dallas": "cowboys", "dallas cowboys": "cowboys",
        "philadelphia": "eagles", "philadelphia eagles": "eagles", "washington": "commanders", "washington commanders": "commanders",
        "pittsburgh": "steelers", "pittsburgh steelers": "steelers", "cleveland": "browns", "cleveland browns": "browns",
        "cincinnati": "bengals", "cincinnati bengals": "bengals", "baltimore": "ravens", "baltimore ravens": "ravens",
        "houston": "texans", "houston texans": "texans", "indianapolis": "colts", "indianapolis colts": "colts",
        "jacksonville": "jaguars", "jacksonville jaguars": "jaguars", "tennessee": "titans", "tennessee titans": "titans",
        "denver": "broncos", "denver broncos": "broncos", "kansas city": "chiefs", "kansas city chiefs": "chiefs",
        "las vegas": "raiders", "las vegas raiders": "raiders", "los angeles chargers": "chargers", "la chargers": "chargers",
        "los angeles rams": "rams", "la rams": "rams", "arizona": "cardinals", "arizona cardinals": "cardinals",
        "seattle": "seahawks", "seattle seahawks": "seahawks", "san francisco 49ers": "49ers", "san francisco": "49ers",
        "green bay": "packers", "green bay packers": "packers", "chicago": "bears", "chicago bears": "bears",
        "detroit": "lions", "detroit lions": "lions", "minnesota": "vikings", "minnesota vikings": "vikings",
        "atlanta": "falcons", "atlanta falcons": "falcons", "carolina": "panthers", "carolina panthers": "panthers",
        "new orleans": "saints", "new orleans saints": "saints", "tampa bay": "buccaneers", "tampa bay buccaneers": "buccaneers",
    },
}

LEAGUE_ALIASES = {
    "ncaafb": "ncaa fb", "ncaa fbs": "ncaa fb", "ncaa football": "ncaa fb",
    "ncaa mens hockey": "ncaa men's hockey", "ncaa womens hockey": "ncaa women's hockey",
    "ncaabb": "ncaa bb", "ncaa mens basketball": "ncaa bb", "ncaa womens basketball": "ncaa wbb",
}
SPORT_BY_LEAGUE = {
    "mlb":"baseball","nba":"basketball","wnba":"basketball","nfl":"football","nhl":"hockey",
    "mls":"soccer","epl":"soccer","ucl":"soccer","laliga":"soccer","serie a":"soccer","bundesliga":"soccer","ligue 1":"soccer",
    "ufc":"mma","f1":"racing","indycar":"racing","pga":"golf","lpga":"golf","liv golf":"golf","atp":"tennis","wta":"tennis",
    "pll":"lacrosse","nll":"lacrosse","nrl":"rugby-league","afl":"australian-football","ncaa fb":"football","ncaa fcs":"football",
    "ncaa bb":"basketball","ncaa wbb":"basketball","ncaa baseball":"baseball","ncaa softball":"softball","ncaa men's hockey":"hockey","ncaa women's hockey":"hockey",
    "ncaa men's soccer":"soccer","ncaa women's soccer":"soccer","ncaa men's lacrosse":"lacrosse","ncaa women's lacrosse":"lacrosse",
    "ncaa men's volleyball":"volleyball","ncaa women's volleyball":"volleyball","ncaa men's water polo":"water-polo","ncaa women's water polo":"water-polo",
    "ncaa women's field hockey":"field-hockey","ncaa beach volleyball":"beach-volleyball",
}
TOLERANCE_MINUTES={"baseball":150,"basketball":120,"football":180,"hockey":150,"soccer":150,"tennis":360,"golf":720,"racing":180,"mma":360,"lacrosse":150,"volleyball":180,"rugby":180,"rugby-league":180,"cricket":180,"australian-football":180,"softball":180,"water-polo":180,"field-hockey":180,"beach-volleyball":180}


def normalize_text(value):
    text=str(value or "").lower().replace("&"," and ")
    text=re.sub(r"\b(at|vs\.?|versus)\b"," ",text)
    return " ".join(re.sub(r"[^a-z0-9]+"," ",text).split())


def normalize_league(value):
    text=normalize_text(value)
    return LEAGUE_ALIASES.get(text.replace(" ",""),text)


def normalize_start(value):
    try:return datetime.fromisoformat(str(value).replace("Z","+00:00")).astimezone(timezone.utc).isoformat().replace("+00:00","Z")
    except Exception:return ""


def _team(value,league):
    text=normalize_text(value); aliases=TEAM_ALIASES.get(league,{})
    if text in aliases:return aliases[text]
    for alias,canonical in aliases.items():
        if len(alias)>5 and alias in text:return canonical
    return text


def _extract_teams(event,league):
    home=event.get("home") or event.get("homeTeam") or event.get("homeTeamName") or ""
    away=event.get("away") or event.get("awayTeam") or event.get("awayTeamName") or ""
    if home or away:return _team(home,league),_team(away,league)
    raw=str(event.get("title") or "")
    parts=re.split(r"\s+@\s+|\s+at\s+|\s+vs\.?\s+|\s+versus\s+",raw,flags=re.I)
    if len(parts)==2:return _team(parts[1],league),_team(parts[0],league)
    return "",""


def _provider_ids(event):
    return {str(event.get(k) or "").strip().lower() for k in ("providerEventId","espnEventId","sportsDbEventId","eventId") if str(event.get(k) or "").strip()}


def canonical_event_key(event):
    league=normalize_league(event.get("league")); sport=SPORT_BY_LEAGUE.get(league,normalize_text(event.get("sport"))); start=normalize_start(event.get("start") or event.get("startUtc"))
    bucket=int(datetime.fromisoformat(start.replace("Z","+00:00")).timestamp()//1800) if start else ""
    home,away=_extract_teams(event,league)
    return (sport,league,home,away,bucket) if home and away else (sport,league,normalize_text(event.get("title")),bucket)


def event_identity(league,title,start,home=None,away=None):
    """Stable ID is based on canonical participants when available, not raw title."""
    league_n=normalize_league(league)
    h,a=_extract_teams({"home":home,"away":away,"title":title},league_n)
    if h and a:
        canonical="|".join((league_n,h,a))
    else:
        canonical="|".join((league_n,normalize_text(title)))
    # Identity is intentionally time-independent for a matchup so a provider
    # correcting the scheduled time does not create a new event. A same-day
    # rematch is handled by the event index using the provider ID/start bucket.
    return "evt_"+hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def identity_match(a,b):
    la,lb=normalize_league(a.get("league")),normalize_league(b.get("league"))
    if not la or la!=lb:return False
    if _provider_ids(a)&_provider_ids(b):return True
    ha,aa=_extract_teams(a,la); hb,ab=_extract_teams(b,lb)
    sa,sb=normalize_start(a.get("start") or a.get("startUtc")),normalize_start(b.get("start") or b.get("startUtc"))
    if not sa or not sb:return False
    ta=datetime.fromisoformat(sa.replace("Z","+00:00")); tb=datetime.fromisoformat(sb.replace("Z","+00:00")); sport=SPORT_BY_LEAGUE.get(la,normalize_text(a.get("sport"))); tolerance=TOLERANCE_MINUTES.get(sport,180)
    if abs((ta-tb).total_seconds())>tolerance*60:return False
    if ha and aa and hb and ab:return ha==hb and aa==ab
    if ha or aa or hb or ab:return False
    return normalize_text(a.get("title"))==normalize_text(b.get("title"))


def merge_event_records(winner,candidate):
    out=dict(winner)
    for key,value in candidate.items():
        if key in {"source","tag"}:continue
        if value not in (None,"",[],{}) and out.get(key) in (None,"",[],{}):out[key]=value
    # Lifecycle/status should come from the freshest non-stale observation.
    wtag=str(out.get("tag") or "").upper(); ctag=str(candidate.get("tag") or "").upper()
    rank={"LIVE":4,"FINAL":3,"UPCOMING":2,"SCHEDULED":2,"STALE_UNKNOWN":1,"PREGAME":1,"":0}
    if rank.get(ctag,0)>rank.get(wtag,0):out["tag"]=candidate.get("tag")
    return out
