#!/usr/bin/env python3
"""Phase 3 presentation metadata; team logos come only from the persistent cache."""
import json
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FEED=ROOT/"data/schedule_feed.json"
CACHE=ROOT/"data/team_logo_map.json"
LEAGUE_ART={"NFL":"https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png","NBA":"https://a.espncdn.com/i/teamlogos/leagues/500/nba.png","WNBA":"https://a.espncdn.com/i/teamlogos/leagues/500/wnba.png","NCAA FB":"https://a.espncdn.com/i/teamlogos/leagues/500/ncaaf.png","NCAA FCS":"https://a.espncdn.com/i/teamlogos/leagues/500/ncaaf.png","NCAA BB":"https://a.espncdn.com/i/teamlogos/leagues/500/ncaab.png","NCAA WBB":"https://a.espncdn.com/i/teamlogos/leagues/500/ncaaw.png","MLB":"https://a.espncdn.com/i/teamlogos/leagues/500/mlb.png","NHL":"https://a.espncdn.com/i/teamlogos/leagues/500/nhl.png","MLS":"https://a.espncdn.com/i/teamlogos/leagues/500/mls.png","EPL":"https://a.espncdn.com/i/teamlogos/soccer/500/23.png","LaLiga":"https://a.espncdn.com/i/teamlogos/soccer/500/15.png","Serie A":"https://a.espncdn.com/i/teamlogos/soccer/500/12.png","Bundesliga":"https://a.espncdn.com/i/teamlogos/soccer/500/10.png","Ligue 1":"https://a.espncdn.com/i/teamlogos/soccer/500/9.png","UCL":"https://a.espncdn.com/i/teamlogos/soccer/500/2.png","UEL":"https://a.espncdn.com/i/teamlogos/soccer/500/1.png","NWSL":"https://a.espncdn.com/i/teamlogos/leagues/500/nwsl.png"}
ALIASES={"ARIZONA":"ARIZONA DIAMONDBACKS","DIAMONDBACKS":"ARIZONA DIAMONDBACKS","D BACKS":"ARIZONA DIAMONDBACKS","DBACKS":"ARIZONA DIAMONDBACKS","AZ":"ARIZONA DIAMONDBACKS","ARIZONA DIAMONDBACKS":"ARIZONA DIAMONDBACKS","ATHLETICS":"ATHLETICS","OAKLAND ATHLETICS":"ATHLETICS","OAKLAND A":"ATHLETICS","OAKLAND AS":"ATHLETICS","ATH":"ATHLETICS","ATLANTA":"ATLANTA BRAVES","BRAVES":"ATLANTA BRAVES","ATL":"ATLANTA BRAVES","ATLANTA BRAVES":"ATLANTA BRAVES","BALTIMORE":"BALTIMORE ORIOLES","ORIOLES":"BALTIMORE ORIOLES","BAL":"BALTIMORE ORIOLES","BALTIMORE ORIOLES":"BALTIMORE ORIOLES","BOSTON":"BOSTON RED SOX","RED SOX":"BOSTON RED SOX","BOS":"BOSTON RED SOX","BOSTON RED SOX":"BOSTON RED SOX","CHICAGO CUBS":"CHICAGO CUBS","CUBS":"CHICAGO CUBS","CHC":"CHICAGO CUBS","CHICAGO WHITE SOX":"CHICAGO WHITE SOX","WHITE SOX":"CHICAGO WHITE SOX","CWS":"CHICAGO WHITE SOX","CHW":"CHICAGO WHITE SOX","CINCINNATI":"CINCINNATI REDS","REDS":"CINCINNATI REDS","CIN":"CINCINNATI REDS","CINCINNATI REDS":"CINCINNATI REDS","CLEVELAND":"CLEVELAND GUARDIANS","GUARDIANS":"CLEVELAND GUARDIANS","CLE":"CLEVELAND GUARDIANS","CLEVELAND GUARDIANS":"CLEVELAND GUARDIANS","COLORADO":"COLORADO ROCKIES","ROCKIES":"COLORADO ROCKIES","COL":"COLORADO ROCKIES","COLORADO ROCKIES":"COLORADO ROCKIES","DETROIT":"DETROIT TIGERS","TIGERS":"DETROIT TIGERS","DET":"DETROIT TIGERS","DETROIT TIGERS":"DETROIT TIGERS","HOUSTON":"HOUSTON ASTROS","ASTROS":"HOUSTON ASTROS","HOU":"HOUSTON ASTROS","HOUSTON ASTROS":"HOUSTON ASTROS","KANSAS CITY":"KANSAS CITY ROYALS","ROYALS":"KANSAS CITY ROYALS","KC":"KANSAS CITY ROYALS","KANSAS CITY ROYALS":"KANSAS CITY ROYALS","LA ANGELS":"LOS ANGELES ANGELS","LOS ANGELES ANGELS":"LOS ANGELES ANGELS","LOS ANGELES ANGELS OF ANAHEIM":"LOS ANGELES ANGELS","ANAHEIM ANGELS":"LOS ANGELES ANGELS","ANGELS":"LOS ANGELES ANGELS","LAA":"LOS ANGELES ANGELS","LA DODGERS":"LOS ANGELES DODGERS","LOS ANGELES DODGERS":"LOS ANGELES DODGERS","DODGERS":"LOS ANGELES DODGERS","LAD":"LOS ANGELES DODGERS","MIAMI":"MIAMI MARLINS","MARLINS":"MIAMI MARLINS","MIA":"MIAMI MARLINS","MIAMI MARLINS":"MIAMI MARLINS","MILWAUKEE":"MILWAUKEE BREWERS","BREWERS":"MILWAUKEE BREWERS","MIL":"MILWAUKEE BREWERS","MILWAUKEE BREWERS":"MILWAUKEE BREWERS","MINNESOTA":"MINNESOTA TWINS","TWINS":"MINNESOTA TWINS","MIN":"MINNESOTA TWINS","MINNESOTA TWINS":"MINNESOTA TWINS","NY METS":"NEW YORK METS","NEW YORK METS":"NEW YORK METS","METS":"NEW YORK METS","NYM":"NEW YORK METS","NY YANKEES":"NEW YORK YANKEES","NEW YORK YANKEES":"NEW YORK YANKEES","YANKEES":"NEW YORK YANKEES","NYY":"NEW YORK YANKEES","PHILADELPHIA":"PHILADELPHIA PHILLIES","PHILLIES":"PHILADELPHIA PHILLIES","PHI":"PHILADELPHIA PHILLIES","PHILADELPHIA PHILLIES":"PHILADELPHIA PHILLIES","PITTSBURGH":"PITTSBURGH PIRATES","PIRATES":"PITTSBURGH PIRATES","PIT":"PITTSBURGH PIRATES","PITTSBURGH PIRATES":"PITTSBURGH PIRATES","SAN DIEGO":"SAN DIEGO PADRES","PADRES":"SAN DIEGO PADRES","SD":"SAN DIEGO PADRES","SDP":"SAN DIEGO PADRES","SAN DIEGO PADRES":"SAN DIEGO PADRES","SAN FRANCISCO":"SAN FRANCISCO GIANTS","SF GIANTS":"SAN FRANCISCO GIANTS","GIANTS":"SAN FRANCISCO GIANTS","SF":"SAN FRANCISCO GIANTS","SFG":"SAN FRANCISCO GIANTS","SAN FRANCISCO GIANTS":"SAN FRANCISCO GIANTS","SEATTLE":"SEATTLE MARINERS","MARINERS":"SEATTLE MARINERS","SEA":"SEATTLE MARINERS","SEATTLE MARINERS":"SEATTLE MARINERS","ST LOUIS":"ST LOUIS CARDINALS","CARDINALS":"ST LOUIS CARDINALS","STL":"ST LOUIS CARDINALS","ST LOUIS CARDINALS":"ST LOUIS CARDINALS","TAMPA BAY":"TAMPA BAY RAYS","RAYS":"TAMPA BAY RAYS","TB":"TAMPA BAY RAYS","TBR":"TAMPA BAY RAYS","TAMPA BAY RAYS":"TAMPA BAY RAYS","TEXAS":"TEXAS RANGERS","RANGERS":"TEXAS RANGERS","TEX":"TEXAS RANGERS","TEXAS RANGERS":"TEXAS RANGERS","TORONTO":"TORONTO BLUE JAYS","BLUE JAYS":"TORONTO BLUE JAYS","TOR":"TORONTO BLUE JAYS","TORONTO BLUE JAYS":"TORONTO BLUE JAYS","WASHINGTON":"WASHINGTON NATIONALS","NATIONALS":"WASHINGTON NATIONALS","WSH":"WASHINGTON NATIONALS","WAS":"WASHINGTON NATIONALS","WASHINGTON NATIONALS":"WASHINGTON NATIONALS"}
def norm(s):return re.sub(r"\s+"," ",re.sub(r"[^A-Z0-9]+"," ",str(s or "").upper())).strip()
def split_matchup(title):
    for p in (r"^(.+?)\s+@\s+(.+)$",r"^(.+?)\s+AT\s+(.+)$",r"^(.+?)\s+(?:VS\.?|VERSUS)\s+(.+)$"):
        m=re.match(p,title.strip(),re.I)
        if m:return m.group(1).strip(),m.group(2).strip()
    return "",""
def load_cache():
    try:
        x=json.loads(CACHE.read_text(encoding="utf-8"));return x if isinstance(x,dict) else {"version":3,"teams":{}}
    except Exception:return {"version":3,"teams":{}}
def cached_logo(cache,league,team):
    teams=cache.setdefault("teams",{});n=norm(team);v=teams.get(f"{league}|{n}")
    if isinstance(v,str) and v:return v
    if league!="MLB":return ""
    canonical=ALIASES.get(n)
    if not canonical:return ""
    for k,target in ALIASES.items():
        if target==canonical:
            v=teams.get(f"MLB|{norm(k)}")
            if isinstance(v,str) and v:return v
    return ""
def main():
    payload=json.loads(FEED.read_text(encoding="utf-8"));events=payload.get("events") or [];cache=load_cache();counts={};fields=games=complete=missing=league_art=named=cleaned=0
    for e in events:
        league=str(e.get("league") or "").strip();old=e.get("title","");title=str(old or "").strip()
        if not title:
            a0=str(e.get("away") or "").strip();h0=str(e.get("home") or "").strip();title=f"{a0} @ {h0}" if a0 and h0 else league
        e["title"]=title;cleaned+=title!=old;e["leagueArt"]=LEAGUE_ART.get(league,"");league_art+=bool(e["leagueArt"]);away,home=split_matchup(title)
        if not away or not home:away=str(e.get("away") or "").strip();home=str(e.get("home") or "").strip()
        if away and home:
            e["eventType"]="team_game";e["away"]=away;e["home"]=home;al=e.get("awayLogo") or cached_logo(cache,league,away);hl=e.get("homeLogo") or cached_logo(cache,league,home);e["awayLogo"]=al;e["homeLogo"]=hl;games+=1;got=int(bool(al))+int(bool(hl));fields+=got;b=counts.setdefault(league,{"team_games":0,"complete":0,"missing":0,"logo_fields":0});b["team_games"]+=1;b["logo_fields"]+=got
            if al and hl:complete+=1;b["complete"]+=1
            else:missing+=1;b["missing"]+=1
        else:
            e["eventType"]="named_event";named+=1
            if not e.get("image") and e["leagueArt"]:e["image"]=e["leagueArt"]
    report={"version":7,"events":len(events),"team_games":games,"team_games_complete":complete,"team_games_missing":missing,"team_logo_fields_populated":fields,"league_art_fields_populated":league_art,"named_events":named,"titles_cleaned":cleaned,"cache_entries":len(cache.get("teams",{})),"external_logo_discovery":False,"team_logo_coverage_by_league":dict(sorted(counts.items())),"rule":"refresh never performs external team-logo discovery; exact cached logos plus deterministic MLB canonical aliases; matchup parser accepts @, at, and vs; named-event cards use league art"}
    payload["phase3VisualReport"]=report;payload["phase3Visuals"]=True;FEED.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8");print(json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
