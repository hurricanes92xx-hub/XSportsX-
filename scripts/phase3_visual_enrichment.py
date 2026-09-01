#!/usr/bin/env python3
"""Phase 3 presentation metadata; team logos come only from the persistent cache."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data/schedule_feed.json"
CACHE = ROOT / "data/team_logo_map.json"

LEAGUE_ART = {
    "NFL":"https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png","NBA":"https://a.espncdn.com/i/teamlogos/leagues/500/nba.png","WNBA":"https://a.espncdn.com/i/teamlogos/leagues/500/wnba.png","NCAA FB":"https://a.espncdn.com/i/teamlogos/leagues/500/ncaaf.png","NCAA FCS":"https://a.espncdn.com/i/teamlogos/leagues/500/ncaaf.png","NCAA BB":"https://a.espncdn.com/i/teamlogos/leagues/500/ncaab.png","NCAA WBB":"https://a.espncdn.com/i/teamlogos/leagues/500/ncaaw.png","MLB":"https://a.espncdn.com/i/teamlogos/leagues/500/mlb.png","NHL":"https://a.espncdn.com/i/teamlogos/leagues/500/nhl.png","MLS":"https://a.espncdn.com/i/teamlogos/leagues/500/mls.png","EPL":"https://a.espncdn.com/i/teamlogos/soccer/500/23.png","LaLiga":"https://a.espncdn.com/i/teamlogos/soccer/500/15.png","Serie A":"https://a.espncdn.com/i/teamlogos/soccer/500/12.png","Bundesliga":"https://a.espncdn.com/i/teamlogos/soccer/500/10.png","Ligue 1":"https://a.espncdn.com/i/teamlogos/soccer/500/9.png","UCL":"https://a.espncdn.com/i/teamlogos/soccer/500/2.png","UEL":"https://a.espncdn.com/i/teamlogos/soccer/500/1.png","NWSL":"https://a.espncdn.com/i/teamlogos/leagues/500/nwsl.png"}

# Canonical MLB identities. These match the current 30-team MLB schedule naming.
MLB_CANONICAL_ALIASES = {
"ARIZONA":"ARIZONA DIAMONDBACKS","ARIZONA DIAMONDBACKS":"ARIZONA DIAMONDBACKS","DIAMONDBACKS":"ARIZONA DIAMONDBACKS","D BACKS":"ARIZONA DIAMONDBACKS","DBACKS":"ARIZONA DIAMONDBACKS","AZ":"ARIZONA DIAMONDBACKS",
"ATHLETICS":"ATHLETICS","OAKLAND ATHLETICS":"ATHLETICS","OAKLAND A":"ATHLETICS","OAKLAND AS":"ATHLETICS","A S":"ATHLETICS","AS":"ATHLETICS","ATH":"ATHLETICS",
"ATLANTA":"ATLANTA BRAVES","ATLANTA BRAVES":"ATLANTA BRAVES","BRAVES":"ATLANTA BRAVES","ATL":"ATLANTA BRAVES",
"BALTIMORE":"BALTIMORE ORIOLES","BALTIMORE ORIOLES":"BALTIMORE ORIOLES","ORIOLES":"BALTIMORE ORIOLES","BAL":"BALTIMORE ORIOLES",
"BOSTON":"BOSTON RED SOX","BOSTON RED SOX":"BOSTON RED SOX","RED SOX":"BOSTON RED SOX","BOS":"BOSTON RED SOX",
"CHICAGO CUBS":"CHICAGO CUBS","CUBS":"CHICAGO CUBS","CHC":"CHICAGO CUBS",
"CHICAGO WHITE SOX":"CHICAGO WHITE SOX","WHITE SOX":"CHICAGO WHITE SOX","CWS":"CHICAGO WHITE SOX","CHW":"CHICAGO WHITE SOX",
"CINCINNATI":"CINCINNATI REDS","CINCINNATI REDS":"CINCINNATI REDS","REDS":"CINCINNATI REDS","CIN":"CINCINNATI REDS",
"CLEVELAND":"CLEVELAND GUARDIANS","CLEVELAND GUARDIANS":"CLEVELAND GUARDIANS","GUARDIANS":"CLEVELAND GUARDIANS","CLE":"CLEVELAND GUARDIANS",
"COLORADO":"COLORADO ROCKIES","COLORADO ROCKIES":"COLORADO ROCKIES","ROCKIES":"COLORADO ROCKIES","COL":"COLORADO ROCKIES",
"DETROIT":"DETROIT TIGERS","DETROIT TIGERS":"DETROIT TIGERS","TIGERS":"DETROIT TIGERS","DET":"DETROIT TIGERS",
"HOUSTON":"HOUSTON ASTROS","HOUSTON ASTROS":"HOUSTON ASTROS","ASTROS":"HOUSTON ASTROS","HOU":"HOUSTON ASTROS",
"KANSAS CITY":"KANSAS CITY ROYALS","KANSAS CITY ROYALS":"KANSAS CITY ROYALS","ROYALS":"KANSAS CITY ROYALS","KC":"KANSAS CITY ROYALS",
"LA ANGELS":"LOS ANGELES ANGELS","LOS ANGELES ANGELS":"LOS ANGELES ANGELS","LOS ANGELES ANGELS OF ANAHEIM":"LOS ANGELES ANGELS","ANAHEIM ANGELS":"LOS ANGELES ANGELS","ANGELS":"LOS ANGELES ANGELS","LAA":"LOS ANGELES ANGELS",
"LA DODGERS":"LOS ANGELES DODGERS","LOS ANGELES DODGERS":"LOS ANGELES DODGERS","DODGERS":"LOS ANGELES DODGERS","LAD":"LOS ANGELES DODGERS",
"MIAMI":"MIAMI MARLINS","MIAMI MARLINS":"MIAMI MARLINS","MARLINS":"MIAMI MARLINS","MIA":"MIAMI MARLINS",
"MILWAUKEE":"MILWAUKEE BREWERS","MILWAUKEE BREWERS":"MILWAUKEE BREWERS","BREWERS":"MILWAUKEE BREWERS","MIL":"MILWAUKEE BREWERS",
"MINNESOTA":"MINNESOTA TWINS","MINNESOTA TWINS":"MINNESOTA TWINS","TWINS":"MINNESOTA TWINS","MIN":"MINNESOTA TWINS",
"NY METS":"NEW YORK METS","NEW YORK METS":"NEW YORK METS","METS":"NEW YORK METS","NYM":"NEW YORK METS",
"NY YANKEES":"NEW YORK YANKEES","NEW YORK YANKEES":"NEW YORK YANKEES","YANKEES":"NEW YORK YANKEES","NYY":"NEW YORK YANKEES",
"PHILADELPHIA":"PHILADELPHIA PHILLIES","PHILADELPHIA PHILLIES":"PHILADELPHIA PHILLIES","PHILLIES":"PHILADELPHIA PHILLIES","PHI":"PHILADELPHIA PHILLIES",
"PITTSBURGH":"PITTSBURGH PIRATES","PITTSBURGH PIRATES":"PITTSBURGH PIRATES","PIRATES":"PITTSBURGH PIRATES","PIT":"PITTSBURGH PIRATES",
"SAN DIEGO":"SAN DIEGO PADRES","SAN DIEGO PADRES":"SAN DIEGO PADRES","PADRES":"SAN DIEGO PADRES","SD":"SAN DIEGO PADRES","SDP":"SAN DIEGO PADRES",
"SAN FRANCISCO":"SAN FRANCISCO GIANTS","SAN FRANCISCO GIANTS":"SAN FRANCISCO GIANTS","SF GIANTS":"SAN FRANCISCO GIANTS","GIANTS":"SAN FRANCISCO GIANTS","SF":"SAN FRANCISCO GIANTS","SFG":"SAN FRANCISCO GIANTS",
"SEATTLE":"SEATTLE MARINERS","SEATTLE MARINERS":"SEATTLE MARINERS","MARINERS":"SEATTLE MARINERS","SEA":"SEATTLE MARINERS",
"ST LOUIS":"ST LOUIS CARDINALS","ST LOUIS CARDINALS":"ST LOUIS CARDINALS","CARDINALS":"ST LOUIS CARDINALS","STL":"ST LOUIS CARDINALS",
"TAMPA BAY":"TAMPA BAY RAYS","TAMPA BAY RAYS":"TAMPA BAY RAYS","RAYS":"TAMPA BAY RAYS","TB":"TAMPA BAY RAYS","TBR":"TAMPA BAY RAYS",
"TEXAS":"TEXAS RANGERS","TEXAS RANGERS":"TEXAS RANGERS","RANGERS":"TEXAS RANGERS","TEX":"TEXAS RANGERS",
"TORONTO":"TORONTO BLUE JAYS","TORONTO BLUE JAYS":"TORONTO BLUE JAYS","BLUE JAYS":"TORONTO BLUE JAYS","TOR":"TORONTO BLUE JAYS",
"WASHINGTON":"WASHINGTON NATIONALS","WASHINGTON NATIONALS":"WASHINGTON NATIONALS","NATIONALS":"WASHINGTON NATIONALS","WSH":"WASHINGTON NATIONALS","WAS":"WASHINGTON NATIONALS"}

# Cache names seen in older/provider feeds. A canonical team may legitimately have
# a logo stored under one of these names. Search these aliases before declaring a
# logo missing; this never performs an external request or fuzzy network lookup.
MLB_CACHE_NAMES = {
"ARIZONA DIAMONDBACKS":["ARIZONA DIAMONDBACKS","DIAMONDBACKS","AZ"],
"ATHLETICS":["ATHLETICS","OAKLAND ATHLETICS","OAKLAND A","OAKLAND AS","ATH"],
"ATLANTA BRAVES":["ATLANTA BRAVES","BRAVES","ATL"],"BALTIMORE ORIOLES":["BALTIMORE ORIOLES","ORIOLES","BAL"],
"BOSTON RED SOX":["BOSTON RED SOX","RED SOX","BOS"],"CHICAGO CUBS":["CHICAGO CUBS","CUBS","CHC"],
"CHICAGO WHITE SOX":["CHICAGO WHITE SOX","WHITE SOX","CWS","CHW"],"CINCINNATI REDS":["CINCINNATI REDS","REDS","CIN"],
"CLEVELAND GUARDIANS":["CLEVELAND GUARDIANS","GUARDIANS","CLE"],"COLORADO ROCKIES":["COLORADO ROCKIES","ROCKIES","COL"],
"DETROIT TIGERS":["DETROIT TIGERS","TIGERS","DET"],"HOUSTON ASTROS":["HOUSTON ASTROS","ASTROS","HOU"],
"KANSAS CITY ROYALS":["KANSAS CITY ROYALS","ROYALS","KC"],"LOS ANGELES ANGELS":["LOS ANGELES ANGELS","LA ANGELS","LOS ANGELES ANGELS OF ANAHEIM","ANAHEIM ANGELS","ANGELS","LAA"],
"LOS ANGELES DODGERS":["LOS ANGELES DODGERS","LA DODGERS","DODGERS","LAD"],"MIAMI MARLINS":["MIAMI MARLINS","MARLINS","MIA"],
"MILWAUKEE BREWERS":["MILWAUKEE BREWERS","BREWERS","MIL"],"MINNESOTA TWINS":["MINNESOTA TWINS","TWINS","MIN"],
"NEW YORK METS":["NEW YORK METS","NY METS","METS","NYM"],"NEW YORK YANKEES":["NEW YORK YANKEES","NY YANKEES","YANKEES","NYY"],
"PHILADELPHIA PHILLIES":["PHILADELPHIA PHILLIES","PHILLIES","PHI"],"PITTSBURGH PIRATES":["PITTSBURGH PIRATES","PIRATES","PIT"],
"SAN DIEGO PADRES":["SAN DIEGO PADRES","PADRES","SAN DIEGO","SD","SDP"],"SAN FRANCISCO GIANTS":["SAN FRANCISCO GIANTS","SF GIANTS","GIANTS","SAN FRANCISCO","SF","SFG"],
"SEATTLE MARINERS":["SEATTLE MARINERS","MARINERS","SEATTLE","SEA"],"ST LOUIS CARDINALS":["ST LOUIS CARDINALS","CARDINALS","ST LOUIS","STL"],
"TAMPA BAY RAYS":["TAMPA BAY RAYS","RAYS","TAMPA BAY","TB","TBR"],"TEXAS RANGERS":["TEXAS RANGERS","RANGERS","TEXAS","TEX"],
"TORONTO BLUE JAYS":["TORONTO BLUE JAYS","BLUE JAYS","TORONTO","TOR"],"WASHINGTON NATIONALS":["WASHINGTON NATIONALS","NATIONALS","WASHINGTON","WSH","WAS"]}

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
    normalized = norm(team)
    direct = teams.get(f"{league}|{normalized}")
    if isinstance(direct, str) and direct: return direct
    if league != "MLB": return ""
    canonical = MLB_CANONICAL_ALIASES.get(normalized)
    if not canonical: return ""
    # First try every known cache spelling for this canonical MLB identity.
    for name in MLB_CACHE_NAMES.get(canonical, [canonical]):
        value = teams.get(f"MLB|{norm(name)}")
        if isinstance(value, str) and value: return value
    # Last-resort deterministic token containment, still cache-only.
    target = set(normalized.split())
    matches=[]
    for k, logo in teams.items():
        if not k.startswith("MLB|") or not isinstance(logo,str) or not logo: continue
        tokens=set(k.split("|",1)[1].split())
        if tokens and (tokens.issubset(target) or target.issubset(tokens)): matches.append(logo)
    logos=set(matches)
    return next(iter(logos)) if len(logos)==1 else ""

def main():
    payload=json.loads(FEED.read_text(encoding="utf-8")); events=payload.get("events") or []; cache=load_cache()
    team_logo_fields=team_games=team_games_complete=team_games_missing=league_art=cleaned=named_events=0; coverage={}
    for event in events:
        league=str(event.get("league") or "").strip(); old_title=event.get("title",""); title=str(old_title or "").strip()
        if not title:
            away0=str(event.get("away") or "").strip(); home0=str(event.get("home") or "").strip(); title=f"{away0} @ {home0}" if away0 and home0 else league
        cleaned += int(title != old_title); event["title"]=title; event["leagueArt"]=LEAGUE_ART.get(league,""); league_art += int(bool(event["leagueArt"]))
        away,home=split_matchup(title)
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
    report={"version":7,"events":len(events),"team_games":team_games,"team_games_complete":team_games_complete,"team_games_missing":team_games_missing,"team_logo_fields_populated":team_logo_fields,"league_art_fields_populated":league_art,"named_events":named_events,"titles_cleaned":cleaned,"cache_entries":len(cache.get("teams",{})),"external_logo_discovery":False,"team_logo_coverage_by_league":dict(sorted(coverage.items())),"rule":"refresh never performs external team-logo discovery; exact cache plus deterministic canonical MLB aliases and known legacy cache spellings only; named-event cards use league art"}
    payload["phase3VisualReport"]=report; payload["phase3Visuals"]=True; FEED.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); print(json.dumps(report,sort_keys=True))
if __name__ == "__main__": main()
