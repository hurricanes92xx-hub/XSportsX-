#!/usr/bin/env python3
"""Independent free shadow-provider layer.

Primary sources remain authoritative. Shadows corroborate/recover live state and
also provide explicit health evidence for leagues whose primary endpoints fail.
"""
from __future__ import annotations
import json, os, re, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

HEADERS={"User-Agent":"XSportsX-ShadowProviders/2.1","Accept":"application/json"}
SPORTSCORE_SPORTS={"football","basketball","cricket","tennis"}
LEAGUE_ALIASES={
 "EPL":{"premierleague","englishpremierleague","premierleagueengland"},"UCL":{"uefachampionsleague","championsleague","uefachampionsleaguequalifying"},
 "UEL":{"uefaeuropa","uefaeuropaleague","europaleague"},"LaLiga":{"laliga","laligasantander","spanishlaliga","laligaespanola"},
 "Serie A":{"seriea","italianseriea","serieatim"},"Bundesliga":{"bundesliga","germanbundesliga","bundesligagermany"},"Ligue 1":{"ligue1","frenchligue1"},
 "MLS":{"mls","majorleaguesoccer","majorleaguesoccerusa"},"NWSL":{"nwsl","nationalwomenssoccerleague"},
 "NBA":{"nba","nationalbasketballassociation"},"WNBA":{"wnba","womensnationalbasketballassociation"},
 "ATP":{"atp","atptour","atpsingles"},"WTA":{"wta","wtatour","wtasingles"},"IPL":{"ipl","indianpremierleague","indianpremierleague2026"},"ICC T20":{"icct20","t20worldcup","internationalcrickett20","iccworldtwenty20"}
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
    req=urllib.request.Request(url,data=data,headers={"User-Agent":"Mozilla/5.0 (XSportsX; +https://github.com/hurricanes92xx-hub/XSportsX-)","Accept":"*/*","Content-Type":"application/x-www-form-urlencoded; charset=utf-8",**(headers or {})},method="POST")
    with urllib.request.urlopen(req,timeout=timeout) as r:return r.read()
def _state(v):
    s=str(v or "").lower().replace("-","_").replace(" ","_")
    if s in {"live","in","in_progress","inprogress","playing","halftime","ht","started","running","set1","set2","set3","set4","set5","set6","set7","inset1","inset2","inset3","inset4","inset5","inset6","inset7"} or "live" in s or s.startswith("inset"):return "LIVE"
    if s in {"final","finished","complete","completed","post","ended","officialresult","closed","corrected"} or "final" in s:return "FINAL"
    return "UPCOMING"
def _league_from_comp(comp):
    if isinstance(comp,dict):
        comp=comp.get("name") or comp.get("displayName") or comp.get("shortName") or comp.get("slug") or comp.get("competitionName") or comp.get("tournamentName") or ""
    n=_norm(comp)
    for league,aliases in LEAGUE_ALIASES.items():
        if n in aliases:return league
    for league,aliases in LEAGUE_ALIASES.items():
        if any(a in n or n in a for a in aliases):return league
    return None

def _name(v):
    if isinstance(v,str): return v.strip()
    if isinstance(v,dict): return str(v.get("name") or v.get("displayName") or v.get("shortName") or v.get("teamName") or "").strip()
    return str(v or "").strip()

def _sportscore(sport):
    root=_get(f"https://sportscore.com/api/widget/matches/?sport={sport}&limit=50&src=xsportsx")
    rows=root.get("matches") if isinstance(root,dict) else root
    out=[]
    for x in rows or []:
        if not isinstance(x,dict):continue
        comp=x.get("competition") or x.get("league") or x.get("tournament") or x.get("event") or ""
        league=_league_from_comp(comp)
        home=_name(x.get("home") or x.get("home_team") or x.get("homeTeam") or x.get("teamA"))
        away=_name(x.get("away") or x.get("away_team") or x.get("awayTeam") or x.get("teamB"))
        start=_iso(x.get("time") or x.get("start") or x.get("date") or x.get("startTime") or x.get("dateTime") or x.get("start_time"))
        if not league or not home or not away:continue
        tag=_state(x.get("status") or x.get("state") or x.get("statusText") or x.get("stage") or x.get("matchStatus"))
        out.append({"league":league,"title":f"{away} @ {home}","start":start,"startUtc":start,"tag":tag,"status":tag,"state":"in" if tag=="LIVE" else "post" if tag=="FINAL" else "pre","home":home,"away":away,"source":"sportscore-shadow","providerEventId":f"sportscore:{x.get('id') or x.get('matchId') or _norm(away)+'-'+_norm(home)+'-'+start}","liveEvidenceSource":"sportscore" if tag=="LIVE" else ""})
    return out

def _fivb_vis():
    """FIVB VIS public live-match feed. Statuses InSet1..InSet7 are LIVE."""
    requests=[
        '<Requests><Request Type="GetVolleyMatchList" Fields="No DateTimeUtc TeamNameA TeamNameB Status Gender TournamentName"><Filter ForLiveScore="true" /></Request></Requests>',
        '<Requests><Request Type="GetVolleyMatchList" Fields="No DateTimeUtc TeamNameA TeamNameB Status TournamentName"><Filter ForLiveScore="true" /></Request></Requests>'
    ]
    raw=None;last=None
    for xml in requests:
        try:
            raw=_post_text("https://www.fivb.org/Vis2009/XmlRequest.asmx",urllib.parse.urlencode({"Request":xml}).encode());break
        except Exception as exc:last=exc
    if raw is None:raise last or RuntimeError("FIVB VIS request failed")
    root=ET.fromstring(raw);out=[]
    for m in root.iter():
        a=m.attrib
        def val(*keys):
            for k in keys:
                if k in a and a[k]:return a[k]
                for child in m:
                    if child.tag.split('}')[-1].lower()==k.lower() and child.text:return child.text.strip()
            return ""
        home=val("TeamNameA","TeamAName");away=val("TeamNameB","TeamBName")
        if not home or not away:continue
        start=_iso(val("DateTimeUtc","BeginDateTimeUtc","DateUtc"))
        status=_state(val("Status","StatusName"))
        gender=_norm(val("Gender","TournamentGender")); tournament=val("TournamentName","Name")
        if gender in {"w","women","female","f"} or "women" in _norm(tournament) or "feminin" in _norm(tournament): league="FIVB Women"
        elif gender in {"m","men","male","male"} or "men" in _norm(tournament): league="FIVB Men"
        else: league="FIVB Men"
        out.append({"league":league,"title":f"{away} @ {home}","start":start,"startUtc":start,"tag":status,"status":status,"state":"in" if status=="LIVE" else "post" if status=="FINAL" else "pre","home":home,"away":away,"source":"fivb-vis-shadow","providerEventId":f"fivb:{val('No','MatchNo','Version') or _norm(home)+'-'+_norm(away)}","liveEvidenceSource":"fivb-vis" if status=="LIVE" else ""})
    return out

def _nascar_truck():
    """NASCAR public feed. Truck is series_id=3."""
    year=datetime.now(timezone.utc).year;last=None;root=None
    urls=[f"https://feed.nascar.com/api/weekendschedule?series_id=3&race_season={year}&v=1",f"https://feedtest.nascar.com/api/weekendschedule?series_id=3&race_season={year}&v=1"]
    for url in urls:
        try: root=_get(url,headers={"Referer":"https://www.nascar.com/","Origin":"https://www.nascar.com/","Accept":"application/json, text/plain, */*"},timeout=10);break
        except Exception as exc:last=exc
    if root is None:raise last or RuntimeError("NASCAR feed unavailable")
    rows=root if isinstance(root,list) else root.get("weekendSchedule") or root.get("data") or root.get("items") or []
    out=[]
    for x in rows:
        if not isinstance(x,dict):continue
        start=_iso(x.get("start_time_utc") or x.get("startTimeUtc") or x.get("start_time"));end=_iso(x.get("end_time_utc") or x.get("endTimeUtc") or x.get("end_time"));
        if not start:continue
        now=datetime.now(timezone.utc);dt=datetime.fromisoformat(start.replace("Z","+00:00"));enddt=datetime.fromisoformat(end.replace("Z","+00:00")) if end else None
        live=dt<=now and (enddt is None or now<=enddt)
        status="LIVE" if live else "UPCOMING";name=str(x.get("event_name") or x.get("eventName") or "NASCAR Truck Race")
        out.append({"league":"NASCAR Truck","title":name,"start":start,"startUtc":start,"tag":status,"status":status,"state":"in" if live else "pre","source":"nascar-public-shadow","providerEventId":f"nascar:{x.get('race_id') or x.get('raceId') or _norm(name)+'-'+start}","liveEvidenceSource":"nascar-public" if live else ""})
    return out

def _cricket_keyed():
    out=[]; failures=[]
    key=os.getenv("CRICKETDATA_API_KEY","").strip()
    if key:
        try:
            root=_get(f"https://api.cricketdata.org/v1/currentMatches?apikey={urllib.parse.quote(key)}&offset=0",timeout=10);rows=root.get("data") or root.get("matches") or []
            for x in rows:
                if not isinstance(x,dict):continue
                names=x.get("name") or "";ti=x.get("teamInfo") or [];home=_name(ti[0] if len(ti)>0 else x.get("homeTeam"));away=_name(ti[1] if len(ti)>1 else x.get("awayTeam"));league=_league_from_comp(names) or ("IPL" if "ipl" in _norm(names) else "ICC T20" if "t20" in _norm(names) else None);start=_iso(x.get("dateTimeGMT") or x.get("dateTime") or x.get("date"));
                if not home or not away or not league:continue
                ended=str(x.get("matchEnded")).lower()=="true";started=str(x.get("matchStarted")).lower()=="true";tag="LIVE" if started and not ended else "FINAL" if ended else "UPCOMING"
                out.append({"league":league,"title":f"{away} @ {home}","start":start,"startUtc":start,"tag":tag,"status":tag,"state":"in" if tag=="LIVE" else "post" if tag=="FINAL" else "pre","home":home,"away":away,"source":"cricketdata-shadow","providerEventId":f"cricketdata:{x.get('id') or _norm(names)}","liveEvidenceSource":"cricketdata" if tag=="LIVE" else ""})
        except Exception as exc:failures.append(f"cricketdata:{type(exc).__name__}")
    key=os.getenv("CRICLIVE_API_KEY","").strip()
    if key:
        try:
            root=_get(f"https://api.cricketliveapi.com/api/v1/matches/live?api_key={urllib.parse.quote(key)}",timeout=10);rows=root.get("data") or root.get("matches") or []
            for x in rows:
                if not isinstance(x,dict):continue
                home=_name(x.get("home_team") or x.get("homeTeam"));away=_name(x.get("away_team") or x.get("awayTeam"));comp=str(x.get("series") or x.get("competition") or "");league="IPL" if "ipl" in _norm(comp) else "ICC T20" if "t20" in _norm(comp) or "icc" in _norm(comp) else None;start=_iso(x.get("start_time") or x.get("startTime") or x.get("date"));
                if home and away and league:out.append({"league":league,"title":f"{away} @ {home}","start":start,"startUtc":start,"tag":"LIVE","status":"LIVE","state":"in","home":home,"away":away,"source":"criclive-shadow","providerEventId":f"criclive:{x.get('id') or _norm(home)+'-'+_norm(away)}","liveEvidenceSource":"criclive"})
        except Exception as exc:failures.append(f"criclive:{type(exc).__name__}")
    return out,failures

def fetch_all():
    out=[];failures=[];counts={}
    for sport in sorted(SPORTSCORE_SPORTS):
        try:rows=_sportscore(sport);out.extend(rows);counts[f"sportscore:{sport}"]=len(rows)
        except Exception as exc:failures.append(f"sportscore:{sport}:{type(exc).__name__}")
    for name,fn in (("fivb",_fivb_vis),("nascar-truck",_nascar_truck)):
        try:rows=fn();out.extend(rows);counts[name]=len(rows)
        except Exception as exc:failures.append(f"{name}:{type(exc).__name__}")
    cricket_rows,cricket_failures=_cricket_keyed();out.extend(cricket_rows);failures.extend(cricket_failures);counts["cricket-keyed"]=len(cricket_rows)
    key=os.getenv("FLASHLIVE_RAPIDAPI_KEY","").strip()
    if key:
        host=os.getenv("FLASHLIVE_RAPIDAPI_HOST","flashlive-sports.p.rapidapi.com").strip()
        try:
            root=_get(f"https://{host}/v1/events/live",{"X-RapidAPI-Key":key,"X-RapidAPI-Host":host},timeout=10);rows=root.get("DATA") or root.get("data") or root.get("events") or []
            for x in rows if isinstance(rows,list) else []:
                if not isinstance(x,dict) or _state(x.get("status") or x.get("stage") or x.get("state"))!="LIVE":continue
                home=_name(x.get("HOME_NAME") or x.get("home_name") or x.get("home"));away=_name(x.get("AWAY_NAME") or x.get("away_name") or x.get("away"));start=_iso(x.get("START_TIME") or x.get("start_time") or x.get("date"));league=_league_from_comp(x.get("TOURNAMENT_NAME") or x.get("competition") or x.get("league"))
                if league and home and away:out.append({"league":league,"title":f"{away} @ {home}","start":start,"startUtc":start,"tag":"LIVE","status":"LIVE","state":"in","home":home,"away":away,"source":"flashlive-shadow","providerEventId":f"flashlive:{x.get('EVENT_ID') or x.get('id') or _norm(away)+'-'+_norm(home)+'-'+start}","liveEvidenceSource":"flashlive"})
        except Exception as exc:failures.append(f"flashlive:{type(exc).__name__}")
    return out,failures,counts
