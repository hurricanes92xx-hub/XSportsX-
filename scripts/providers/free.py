#!/usr/bin/env python3
"""Keyless/free sports providers used as secondary evidence."""
from __future__ import annotations
import json, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta
HEADERS={"User-Agent":"XSportsX-Schedule/1.0","Accept":"application/json"}

def _get(url,timeout=10):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode("utf-8","ignore"))

def _iso(value):
    if not value:return ""
    try:return datetime.fromisoformat(str(value).replace("Z","+00:00")).astimezone(timezone.utc).isoformat().replace("+00:00","Z")
    except Exception:return str(value)

def _norm(value):return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())

def _status(value):
    s=str(value or "").lower().replace("-","_").replace(" ","_")
    if s in {"live","in","in_progress","inprogress","playing","1h","2h","ht"}:return "LIVE"
    if s in {"final","finished","complete","completed","post","ended"}:return "FINAL"
    return "UPCOMING"

def _competition_matches(value,league):
    aliases={"EPL":{"englishpremierleague","premierleague"},"UCL":{"uefachampionsleague","championsleague"},"UEL":{"uefaeuropaleague","europaleague"},"LaLiga":{"laliga","spanishlaliga"},"Serie A":{"seriea","italianseriea"},"Bundesliga":{"bundesliga","germanbundesliga"},"Ligue 1":{"ligue1","frenchligue1"},"MLS":{"mls","majorleaguesoccer"},"NWSL":{"nwsl","nationalwomenssoccerleague"},"NBA":{"nba","nationalbasketballassociation"},"WNBA":{"wnba","womensnationalbasketballassociation"},"IPL":{"ipl","indianpremierleague"},"ICC T20":{"icct20","t20worldcup","internationalcrickett20"},"ATP":{"atp","atptour"},"WTA":{"wta","wtatour"}}
    return _norm(value) in aliases.get(league,set())

def _espn_fallback(league,icon):
    mapping={"NWSL":("soccer","usa.nwsl"),"UEL":("soccer","uefa.europa"),"MLS":("soccer","usa.1")}
    row=mapping.get(league)
    if not row:return False,[]
    sport,slug=row; start=datetime.now(timezone.utc).date(); end=start+timedelta(days=30)
    url=f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/scoreboard?dates={start:%Y%m%d}-{end:%Y%m%d}&limit=1000"
    try:
        root=_get(url,timeout=8); raw=root.get("events") if isinstance(root,dict) else []; out=[]
        for event in raw or []:
            comp=(event.get("competitions") or [{}])[0]; teams=comp.get("competitors") or []
            home=next((x.get("team",{}).get("shortDisplayName") or x.get("team",{}).get("displayName") for x in teams if x.get("homeAway")=="home"),"")
            away=next((x.get("team",{}).get("shortDisplayName") or x.get("team",{}).get("displayName") for x in teams if x.get("homeAway")=="away"),"")
            if not event.get("date") or not home or not away:continue
            state=str(((comp.get("status") or {}).get("type") or {}).get("state") or "pre").lower()
            out.append({"league":league,"title":f"{away} @ {home}","start":event["date"],"tag":"LIVE" if state=="in" else "FINAL" if state=="post" else "UPCOMING","icon":icon,"source":"espn-shadow","home":home,"away":away,"providerEventId":f"espn:{event['id']}" if event.get("id") else f"espn:{_norm(away)}-{_norm(home)}-{event['date']}"})
        return True,out
    except Exception:return False,[]

def sportscore(league,icon):
    sport_by_league={"EPL":"football","UCL":"football","UEL":"football","LaLiga":"football","Serie A":"football","Bundesliga":"football","Ligue 1":"football","MLS":"football","NWSL":"football","NBA":"basketball","WNBA":"basketball","IPL":"cricket","ICC T20":"cricket","ATP":"tennis","WTA":"tennis"}
    sport=sport_by_league.get(league)
    if not sport:return True,[],"unsupported league for SportScore"
    url="https://sportscore.com/api/widget/matches/?"+urllib.parse.urlencode({"sport":sport,"limit":50,"src":"XSportsX"})
    try:
        root=_get(url,timeout=8); rows=root.get("matches") if isinstance(root,dict) else root; out=[]
        for item in rows or []:
            if not isinstance(item,dict):continue
            competition=item.get("competition") or item.get("league") or ""
            if _norm(competition)!=_norm(league) and not _competition_matches(competition,league):continue
            home=str(item.get("home") or item.get("home_team") or "").strip(); away=str(item.get("away") or item.get("away_team") or "").strip(); start=_iso(item.get("time") or item.get("start") or item.get("date"))
            if not home or not away or not start:continue
            out.append({"league":league,"title":f"{away} @ {home}","start":start,"tag":_status(item.get("status")),"icon":icon,"source":"sportscore","home":home,"away":away,"providerEventId":f"sportscore:{item.get('id') or _norm(away)+'-'+_norm(home)+'-'+start}","attribution":"SportScore"})
        if out:return True,out,""
        ok,shadow=_espn_fallback(league,icon)
        if ok and shadow:return True,shadow,""
        return True,[],""
    except Exception as exc:
        ok,shadow=_espn_fallback(league,icon)
        if ok and shadow:return True,shadow,""
        return False,[],f"{type(exc).__name__}: {exc}"

def jolpica_f1(league,icon):
    if league!="F1":return True,[],"unsupported league for Jolpica"
    year=datetime.now(timezone.utc).year
    try:
        root=_get(f"https://api.jolpi.ca/ergast/f1/{year}.json",timeout=8); races=(((root.get("MRData") or {}).get("RaceTable") or {}).get("Races") or []); out=[]
        for race in races:
            name=race.get("raceName") or race.get("Circuit",{}).get("circuitName") or "Formula 1"; date=race.get("date"); tm=race.get("time") or "00:00:00Z"
            if date:out.append({"league":"F1","title":name,"start":_iso(f"{date}T{tm}"),"tag":"UPCOMING","icon":icon,"source":"jolpica-f1","providerEventId":f"jolpica:{race.get('round') or name}"})
        return True,out,""
    except Exception as exc:return False,[],f"{type(exc).__name__}: {exc}"

def openf1(league,icon):
    if league!="F1":return True,[],"unsupported league for OpenF1"
    try:
        rows=_get("https://api.openf1.org/v1/sessions?session_key=latest",timeout=8); rows=rows if isinstance(rows,list) else []; now=datetime.now(timezone.utc); out=[]
        for item in rows:
            start_dt=datetime.fromisoformat(str(item.get("date_start") or "").replace("Z","+00:00")) if item.get("date_start") else None
            end_dt=datetime.fromisoformat(str(item.get("date_end") or "").replace("Z","+00:00")) if item.get("date_end") else None
            start=_iso(item.get("date_start") or item.get("date_end")); name=item.get("session_name") or item.get("meeting_name") or "Formula 1"
            if not start:continue
            tag="LIVE" if start_dt and (end_dt is None or start_dt<=now<=end_dt) else "FINAL" if end_dt and now>end_dt else "UPCOMING"
            out.append({"league":"F1","title":name,"start":start,"tag":tag,"icon":icon,"source":"openf1","providerEventId":f"openf1:{item.get('session_key') or start}"})
        return True,out,""
    except Exception as exc:return False,[],f"{type(exc).__name__}: {exc}"

def openliga(league,icon):
    if league!="Bundesliga":return True,[],"unsupported league for OpenLigaDB"
    try:
        year=datetime.now(timezone.utc).year; root=_get(f"https://api.openligadb.de/getmatchdata/bl1/{year}",timeout=8); out=[]
        for item in root if isinstance(root,list) else []:
            h=((item.get("team1") or {}).get("teamName") or "").strip(); a=((item.get("team2") or {}).get("teamName") or "").strip(); start=_iso(item.get("matchDateTimeUTC") or item.get("matchDateTime"))
            if h and a and start:out.append({"league":"Bundesliga","title":f"{a} @ {h}","start":start,"tag":"FINAL" if item.get("matchIsFinished") else "UPCOMING","icon":icon,"source":"openligadb","home":h,"away":a,"providerEventId":f"openligadb:{item.get('matchID') or start}"})
        return True,out,""
    except Exception as exc:return False,[],f"{type(exc).__name__}: {exc}"

def fetch(provider,league,icon):
    if provider=="sportscore":return sportscore(league,icon)
    if provider=="jolpica-f1":return jolpica_f1(league,icon)
    if provider=="openf1":return openf1(league,icon)
    if provider=="openligadb":return openliga(league,icon)
    return False,[],"unknown free provider"
