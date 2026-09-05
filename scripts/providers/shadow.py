#!/usr/bin/env python3
"""Independent free shadow-provider layer.

Primary sources remain authoritative. Shadows corroborate/recover live state and
also provide explicit health evidence for leagues whose primary endpoints fail.
"""
from __future__ import annotations
import json, os, re, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

HEADERS={"User-Agent":"XSportsX-ShadowProviders/2.0","Accept":"application/json"}
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
def _post_text(url,data,headers=None,timeout=10):
    req=urllib.request.Request(url,data=data,headers={"User-Agent":HEADERS["User-Agent"],"Accept":"application/json","Content-Type":"application/x-www-form-urlencoded; charset=utf-8",**(headers or {})},method="POST")
    with urllib.request.urlopen(req,timeout=timeout) as r:return r.read()
def _state(v):
    s=str(v or "").lower().replace("-","_").replace(" ","_")
    if s in {"live","in","in_progress","inprogress","playing","halftime","ht","started"} or "live" in s:return "LIVE"
    if s in {"final","finished","complete","completed","post","ended"} or "final" in s:return "FINAL"
    return "UPCOMING"
def _league_from_comp(comp):
    if isinstance(comp,dict): comp=comp.get("name") or comp.get("displayName") or comp.get("shortName") or ""
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
        comp=x.get("competition") or x.get("league") or ""; league=_league_from_comp(comp)
        home=str(x.get("home") or x.get("home_team") or (x.get("homeTeam") or {}).get("name") or "").strip()
        away=str(x.get("away") or x.get("away_team") or (x.get("awayTeam") or {}).get("name") or "").strip()
        start=_iso(x.get("time") or x.get("start") or x.get("date") or x.get("startTime"))
        if not league or not home or not away or not start:continue
        tag=_state(x.get("status") or x.get("state") or x.get("statusText"))
        out.append({"league":league,"title":f"{away} @ {home}","start":start,"startUtc":start,"tag":tag,"status":tag,"state":"in" if tag=="LIVE" else "post" if tag=="FINAL" else "pre","home":home,"away":away,"source":"sportscore-shadow","providerEventId":f"sportscore:{x.get('id') or _norm(away)+'-'+_norm(home)+'-'+start}","liveEvidenceSource":"sportscore" if tag=="LIVE" else ""})
    return out

def _fivb_vis():
    """Use FIVB's public VIS service; no login is required for public data."""
    xml='''<Requests><Request Type="GetVolleyMatchList" Fields="No DateTimeUtc TeamNameA TeamNameB Status MatchPointsA MatchPointsB TournamentName" ><Filter ForLiveScore="true" /></Request></Requests>'''
    raw=_post_text("https://www.fivb.org/Vis2009/XmlRequest.asmx",urllib.parse.urlencode({"Request":xml}).encode())
    root=ET.fromstring(raw);out=[]
    for m in root.iter():
        if not m.tag.lower().endswith("volleyballmatch"):continue
        a=m.attrib;home=a.get("TeamNameA") or a.get("TeamAName") or "";away=a.get("TeamNameB") or a.get("TeamBName") or "";start=_iso(a.get("DateTimeUtc") or a.get("DateUtc"))
        if not home or not away:continue
        status=_state(a.get("Status") or a.get("StatusName"))
        out.append({"league":"FIVB Men" if str(a.get("Gender") or "").lower().startswith("m") else "FIVB Women","title":f"{away} @ {home}","start":start,"startUtc":start,"tag":status,"status":status,"state":"in" if status=="LIVE" else "pre","home":home,"away":away,"source":"fivb-vis-shadow","providerEventId":f"fivb:{a.get('No') or a.get('Version') or _norm(home)+'-'+_norm(away)}","liveEvidenceSource":"fivb-vis" if status=="LIVE" else ""})
    return out

def _nascar_truck():
    """NASCAR public feed. Truck is series_id=3; derive live from current run timing."""
    year=datetime.now(timezone.utc).year
    root=_get(f"https://feed.nascar.com/api/weekendschedule?series_id=3&race_season={year}&v=1",timeout=10)
    rows=root if isinstance(root,list) else root.get("weekendSchedule") or root.get("data") or root.get("items") or []
    out=[]
    for x in rows:
        if not isinstance(x,dict):continue
        start=_iso(x.get("start_time_utc") or x.get("startTimeUtc") or x.get("start_time"));end=_iso(x.get("end_time_utc") or x.get("endTimeUtc") or x.get("end_time"));
        if not start:continue
        now=datetime.now(timezone.utc);dt=datetime.fromisoformat(start.replace("Z","+00:00"));enddt=datetime.fromisoformat(end.replace("Z","+00:00")) if end else None
        live=dt<=now and (enddt is None or now<=enddt)
        status="LIVE" if live else "UPCOMING"
        name=str(x.get("event_name") or x.get("eventName") or "NASCAR Truck Race")
        out.append({"league":"NASCAR Truck","title":name,"start":start,"startUtc":start,"tag":status,"status":status,"state":"in" if live else "pre","source":"nascar-public-shadow","providerEventId":f"nascar:{x.get('race_id') or x.get('raceId') or _norm(name)+'-'+start}","liveEvidenceSource":"nascar-public" if live else ""})
    return out

def _cricket_keyed():
    """Optional free cricket APIs. Keys are free-tier credentials, never hard-coded."""
    out=[]; failures=[]
    key=os.getenv("CRICKETDATA_API_KEY","").strip()
    if key:
        try:
            root=_get(f"https://api.cricketdata.org/v1/currentMatches?apikey={urllib.parse.quote(key)}&offset=0",timeout=10)
            rows=root.get("data") or root.get("matches") or []
            for x in rows:
                if not isinstance(x,dict):continue
                names=x.get("name") or ""; home=str(x.get("teamInfo",[{},{}])[0].get("name") if isinstance(x.get("teamInfo"),list) and x.get("teamInfo") else "");away=str(x.get("teamInfo",[{},{}])[1].get("name") if isinstance(x.get("teamInfo"),list) and len(x.get("teamInfo"))>1 else "")
                if not home or not away:continue
                league=_league_from_comp(names) or ("IPL" if "ipl" in _norm(names) else "ICC T20" if "t20" in _norm(names) else None)
                if not league:continue
                start=_iso(x.get("dateTimeGMT") or x.get("dateTime") or x.get("date"));tag="LIVE" if str(x.get("matchStarted")).lower()=="true" and str(x.get("matchEnded")).lower()!="true" else "FINAL" if str(x.get("matchEnded")).lower()=="true" else "UPCOMING"
                out.append({"league":league,"title":f"{away} @ {home}","start":start,"startUtc":start,"tag":tag,"status":tag,"state":"in" if tag=="LIVE" else "post" if tag=="FINAL" else "pre","home":home,"away":away,"source":"cricketdata-shadow","providerEventId":f"cricketdata:{x.get('id') or _norm(names)}","liveEvidenceSource":"cricketdata" if tag=="LIVE" else ""})
        except Exception as exc:failures.append(f"cricketdata:{type(exc).__name__}")
    key=os.getenv("CRICLIVE_API_KEY","").strip()
    if key:
        try:
            root=_get(f"https://api.cricketliveapi.com/api/v1/matches/live?api_key={urllib.parse.quote(key)}",timeout=10)
            rows=root.get("data") or root.get("matches") or []
            for x in rows:
                if not isinstance(x,dict):continue
                home=str(x.get("home_team") or x.get("homeTeam") or "");away=str(x.get("away_team") or x.get("awayTeam") or "");
                if not home or not away:continue
                comp=str(x.get("series") or x.get("competition") or "");league="IPL" if "ipl" in _norm(comp) else "ICC T20" if "t20" in _norm(comp) or "icc" in _norm(comp) else None
                if not league:continue
                start=_iso(x.get("start_time") or x.get("startTime") or x.get("date"));out.append({"league":league,"title":f"{away} @ {home}","start":start,"startUtc":start,"tag":"LIVE","status":"LIVE","state":"in","home":home,"away":away,"source":"criclive-shadow","providerEventId":f"criclive:{x.get('id') or _norm(home)+'-'+_norm(away)}","liveEvidenceSource":"criclive"})
        except Exception as exc:failures.append(f"criclive:{type(exc).__name__}")
    return out,failures

def fetch_all():
    out=[]; failures=[]; counts={}
    for sport in sorted(SPORTSCORE_SPORTS):
        try:
            rows=_sportscore(sport);out.extend(rows);counts[f"sportscore:{sport}"]=len(rows)
        except Exception as exc:failures.append(f"sportscore:{sport}:{type(exc).__name__}")
    for name,fn in (("fivb",_fivb_vis),("nascar-truck",_nascar_truck)):
        try:
            rows=fn();out.extend(rows);counts[name]=len(rows)
        except Exception as exc:failures.append(f"{name}:{type(exc).__name__}")
    cricket_rows,cricket_failures=_cricket_keyed();out.extend(cricket_rows);failures.extend(cricket_failures);counts["cricket-keyed"]=len(cricket_rows)
    key=os.getenv("FLASHLIVE_RAPIDAPI_KEY","").strip()
    if key:
        host=os.getenv("FLASHLIVE_RAPIDAPI_HOST","flashlive-sports.p.rapidapi.com").strip()
        try:
            root=_get(f"https://{host}/v1/events/live",{"X-RapidAPI-Key":key,"X-RapidAPI-Host":host},timeout=10)
            rows=root.get("DATA") or root.get("data") or root.get("events") or []
            for x in rows if isinstance(rows,list) else []:
                if not isinstance(x,dict) or _state(x.get("status") or x.get("stage") or x.get("state"))!="LIVE":continue
                home=str(x.get("HOME_NAME") or x.get("home_name") or x.get("home") or "").strip();away=str(x.get("AWAY_NAME") or x.get("away_name") or x.get("away") or "").strip();start=_iso(x.get("START_TIME") or x.get("start_time") or x.get("date"));league=_league_from_comp(x.get("TOURNAMENT_NAME") or x.get("competition") or x.get("league"))
                if league and home and away:out.append({"league":league,"title":f"{away} @ {home}","start":start,"startUtc":start,"tag":"LIVE","status":"LIVE","state":"in","home":home,"away":away,"source":"flashlive-shadow","providerEventId":f"flashlive:{x.get('EVENT_ID') or x.get('id') or _norm(away)+'-'+_norm(home)+'-'+start}","liveEvidenceSource":"flashlive"})
        except Exception as exc:failures.append(f"flashlive:{type(exc).__name__}")
    return out,failures,counts
