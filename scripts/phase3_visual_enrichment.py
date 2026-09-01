#!/usr/bin/env python3
"""Phase 3 presentation metadata; team logos come only from the persistent cache."""
# v5: deterministic MLB alias fallback; no external logo discovery.
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data/schedule_feed.json"
CACHE = ROOT / "data/team_logo_map.json"

LEAGUE_ART = {
    "NFL":"https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png","NBA":"https://a.espncdn.com/i/teamlogos/leagues/500/nba.png","WNBA":"https://a.espncdn.com/i/teamlogos/leagues/500/wnba.png","NCAA FB":"https://a.espncdn.com/i/teamlogos/leagues/500/ncaaf.png","NCAA FCS":"https://a.espncdn.com/i/teamlogos/leagues/500/ncaaf.png","NCAA BB":"https://a.espncdn.com/i/teamlogos/leagues/500/ncaab.png","NCAA WBB":"https://a.espncdn.com/i/teamlogos/leagues/500/ncaaw.png","MLB":"https://a.espncdn.com/i/teamlogos/leagues/500/mlb.png","NHL":"https://a.espncdn.com/i/teamlogos/leagues/500/nhl.png","MLS":"https://a.espncdn.com/i/teamlogos/leagues/500/mls.png","EPL":"https://a.espncdn.com/i/teamlogos/soccer/500/23.png","LaLiga":"https://a.espncdn.com/i/teamlogos/soccer/500/15.png","Serie A":"https://a.espncdn.com/i/teamlogos/soccer/500/12.png","Bundesliga":"https://a.espncdn.com/i/teamlogos/soccer/500/10.png","Ligue 1":"https://a.espncdn.com/i/teamlogos/soccer/500/9.png","UCL":"https://a.espncdn.com/i/teamlogos/soccer/500/2.png","UEL":"https://a.espncdn.com/i/teamlogos/soccer/500/1.png","NWSL":"https://a.espncdn.com/i/teamlogos/leagues/500/nwsl.png"}

def norm(s):
    s = re.sub(r"[^A-Z0-9]+", " ", str(s or "").upper())
    return re.sub(r"\s+", " ", s).strip()

def split_matchup(title):
    for pattern in (r"^(.+?)\s+@\s+(.+)$", r"^(.+?)\s+(?:VS\.?|VERSUS)\s+(.+)$"):
        m = re.match(pattern, title.strip(), re.I)
        if m: return m.group(1).strip(), m.group(2).strip()
    return "", ""

def load_cache():
    try:
        raw = json.loads(CACHE.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {"version": 3, "teams": {}}
    except Exception:
        return {"version": 3, "teams": {}}

def cached_logo(cache, league, team):
    teams = cache.setdefault("teams", {})
    key = f"{league}|{norm(team)}"
    value = teams.get(key)
    if isinstance(value, str) and value:
        return value
    if league == "MLB":
        target = set(norm(team).split())
        if not target: return ""
        matches = []
        for k, logo in teams.items():
            if not k.startswith("MLB|") or not isinstance(logo, str) or not logo: continue
            tokens = set(k.split("|", 1)[1].split())
            if tokens and (tokens.issubset(target) or target.issubset(tokens)):
                matches.append((len(tokens), logo))
        logos = {logo for _, logo in matches}
        if len(logos) == 1: return next(iter(logos))
    return ""

def main():
    payload = json.loads(FEED.read_text(encoding="utf-8")); events = payload.get("events") or []; cache = load_cache()
    team_logo_fields = team_games = team_games_complete = team_games_missing = league_art = cleaned = named_events = 0; coverage = {}
    for event in events:
        league = str(event.get("league") or "").strip(); old_title = event.get("title", ""); title = str(old_title or "").strip()
        if not title:
            away0=str(event.get("away") or "").strip(); home0=str(event.get("home") or "").strip(); title=f"{away0} @ {home0}" if away0 and home0 else league
        cleaned += int(title != old_title); event["title"] = title; event["leagueArt"] = LEAGUE_ART.get(league, ""); league_art += int(bool(event["leagueArt"]))
        away, home = split_matchup(title)
        if not away and not home: away=str(event.get("away") or "").strip(); home=str(event.get("home") or "").strip()
        if away and home:
            event["eventType"]="team_game"; event["away"]=away; event["home"]=home
            a=event.get("awayLogo") or cached_logo(cache,league,away); h=event.get("homeLogo") or cached_logo(cache,league,home); event["awayLogo"]=a; event["homeLogo"]=h
            team_games+=1; fields=int(bool(a))+int(bool(h)); team_logo_fields+=fields; bucket=coverage.setdefault(league,{"team_games":0,"complete":0,"missing":0,"logo_fields":0}); bucket["team_games"]+=1; bucket["logo_fields"]+=fields
            if a and h: team_games_complete+=1; bucket["complete"]+=1
            else: team_games_missing+=1; bucket["missing"]+=1
        else:
            event["eventType"]="named_event"; named_events+=1
            if not event.get("image") and event["leagueArt"]: event["image"]=event["leagueArt"]
    report={"version":5,"events":len(events),"team_games":team_games,"team_games_complete":team_games_complete,"team_games_missing":team_games_missing,"team_logo_fields_populated":team_logo_fields,"league_art_fields_populated":league_art,"named_events":named_events,"titles_cleaned":cleaned,"cache_entries":len(cache.get("teams",{})),"external_logo_discovery":False,"team_logo_coverage_by_league":dict(sorted(coverage.items())),"rule":"refresh never performs external team-logo discovery; exact cached logos plus deterministic MLB alias fallback only; named-event cards use league art"}
    payload["phase3VisualReport"]=report; payload["phase3Visuals"]=True; FEED.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); print(json.dumps(report,sort_keys=True))
if __name__ == "__main__": main()
