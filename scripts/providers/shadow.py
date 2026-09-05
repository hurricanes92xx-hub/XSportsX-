#!/usr/bin/env python3
"""Free shadow-provider layer for independent live-state evidence.

Primary sources remain authoritative. These providers are used only to corroborate
or recover events when the primary feed is unavailable. SportScore is keyless and
covers football, basketball, cricket and tennis. FlashLive is optional when a free
RapidAPI key is configured and can extend the shadow layer to additional sports.
"""
from __future__ import annotations
import json, os, re, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

HEADERS={"User-Agent":"XSportsX-ShadowProviders/1.0","Accept":"application/json"}

SPORTSCORE_SPORTS={"football","basketball","cricket","tennis"}
LEAGUE_ALIASES={
 "EPL":{"premierleague","englishpremierleague"},"UCL":{"uefachampionsleague","championsleague"},
 "UEL":{"uefaeuropa","uefaeuropaleague","europaleague"},"LaLiga":{"laliga","laligasantander","spanishlaliga"},
 "Serie A":{"seriea","italianseriea"},"Bundesliga":{"bundesliga","germanbundesliga"},"Ligue 1":{"ligue1","frenchligue1"},
 "MLS":{"mls","majorleaguesoccer"},"NWSL":{"nwsl","nationalwomenssoccerleague"},
 "NBA":{"nba","nationalbasketballassociation"},"WNBA":{"wnba","womensnationalbasketballassociation"},
 "ATP":{"atp","atptour"},"WTA":{"wta","wtatour"},"IPL":{"ipl","indianpremierleague"},"ICC T20":{"icct20","t20worldcup","internationalcrickett20"}
}

def _norm(v): return re.sub(r"[^a-z0-9]+","",str(v or "").lower())
def _iso(v):
    if not v:return ""
    try:return datetime.fromisoformat(str(v).replace("Z","+00:00")).astimezone(timezone.utc).isoformat().replace("+00:00","Z")
    except Exception:return ""
def _get(url,headers=None,timeout=8):
    req=urllib.request.Request(url,headers={**HEADERS,**(headers or {})})
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode("utf-8","ignore"))
def _state(v):
    s=str(v or "").lower().replace("-","_").replace(" ","_")
    if s in {"live","in","in_progress","inprogress","playing","halftime","ht"} or "live" in s:return "LIVE"
    if s in {"final","finished","complete","completed","post","ended"} or "final" in s:return "FINAL"
    return "UPCOMING"
def _league_from_comp(comp):
    n=_norm(comp)
    for league,aliases in LEAGUE_ALIASES.items():
        if n in aliases:return league
    return None

def _sportscore(sport):
    root=_get(f"https://sportscore.com/api/widget/matches/?sport={sport}&limit=50&src=xsportsx")
    rows=root.get("matches") if isinstance(root,dict) else root
    out=[]
    for x in rows or []:
        if not isinstance(x,dict):continue
        comp=str(x.get("competition") or x.get("league") or "").strip(); league=_league_from_comp(comp)
        if not league:continue
        home=str(x.get("home") or x.get("home_team") or "").strip(); away=str(x.get("away") or x.get("away_team") or "").strip(); start=_iso(x.get("time") or x.get("start") or x.get("date"))
        if not home or not away or not start:continue
        tag=_state(x.get("status") or x.get("state"))
        out.append({"league":league,"title":f"{away} @ {home}","start":start,"startUtc":start,"tag":tag,"status":tag,"state":"in" if tag=="LIVE" else "post" if tag=="FINAL" else "pre","home":home,"away":away,"source":"sportscore-shadow","providerEventId":f"sportscore:{x.get('id') or _norm(away)+'-'+_norm(home)+'-'+start}","liveEvidenceSource":"sportscore" if tag=="LIVE" else ""})
    return out

def fetch_all():
    out=[]; failures=[]; counts={}
    for sport in sorted(SPORTSCORE_SPORTS):
        try:
            rows=_sportscore(sport);out.extend(rows);counts[sport]=len(rows)
        except Exception as exc:failures.append(f"sportscore:{sport}:{type(exc).__name__}")
    # Optional free-tier FlashLive broadens coverage when the user configures a key.
    key=os.getenv("FLASHLIVE_RAPIDAPI_KEY","").strip()
    if key:
        host=os.getenv("FLASHLIVE_RAPIDAPI_HOST","flashlive-sports.p.rapidapi.com").strip()
        # Keep this adapter conservative: only consume a documented live endpoint
        # and accept records whose response explicitly identifies a live state.
        try:
            url=f"https://{host}/v1/events/live"
            root=_get(url,{"X-RapidAPI-Key":key,"X-RapidAPI-Host":host},timeout=10)
            rows=root.get("DATA") or root.get("data") or root.get("events") or []
            for x in rows if isinstance(rows,list) else []:
                if not isinstance(x,dict):continue
                status=_state(x.get("status") or x.get("stage") or x.get("state"))
                if status!="LIVE":continue
                home=str(x.get("HOME_NAME") or x.get("home_name") or x.get("home") or "").strip();away=str(x.get("AWAY_NAME") or x.get("away_name") or x.get("away") or "").strip();start=_iso(x.get("START_TIME") or x.get("start_time") or x.get("date"))
                league=_league_from_comp(x.get("TOURNAMENT_NAME") or x.get("competition") or x.get("league"))
                if league and home and away and start:out.append({"league":league,"title":f"{away} @ {home}","start":start,"startUtc":start,"tag":"LIVE","status":"LIVE","state":"in","home":home,"away":away,"source":"flashlive-shadow","providerEventId":f"flashlive:{x.get('EVENT_ID') or x.get('id') or _norm(away)+'-'+_norm(home)+'-'+start}","liveEvidenceSource":"flashlive"})
        except Exception as exc:failures.append(f"flashlive:{type(exc).__name__}")
    return out,failures,counts
