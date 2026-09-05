#!/usr/bin/env python3
"""Fast, provider-first live-state reconciliation across every configured league."""
from __future__ import annotations
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
from refresh_schedules_legacy import ESPN_LEAGUES
from providers.ncaa import NCAA_LEAGUES, _fetch_espn_day
from event_identity import event_identity
ROOT=Path(__file__).resolve().parents[1]
FEED=ROOT/"data"/"schedule_feed.json"
HEADERS={"User-Agent":"XSportsX-LiveSweep/1.2","Accept":"application/json, */*","Accept-Language":"en-US,en;q=0.9"}
MAX_LIVE_HOURS={"baseball":5.0,"basketball":3.5,"football":5.0,"hockey":4.0,"soccer":3.5,"tennis":5.0,"volleyball":4.0,"golf":10.0,"racing":8.0,"mma":6.0,"boxing":6.0,"wrestling":5.0,"lacrosse":3.5,"rugby":3.5,"rugby-league":3.5,"cricket":10.0,"australian-football":4.0}

def _get(url):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=8) as response:return response.read()

def _fetch_league(meta):
    name,sport,league,icon,_days=meta;today=datetime.now(timezone.utc).strftime("%Y%m%d")
    base=f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={today}&limit=1000";last=None
    for url in (base.replace("https://site.api.espn.com","https://site.web.api.espn.com"),base):
        try:
            root=json.loads(_get(url));raw=root.get("events");return name,raw if isinstance(raw,list) else [],None
        except Exception as exc:last=str(exc)
    return name,[],last

def _fetch_ncaa(meta):
    name,sport,division,icon=meta
    try:
        events=_fetch_espn_day(name,datetime.now(timezone.utc).date())
        return name,events,None
    except Exception as exc:
        return name,[],str(exc)

def _state(status):
    typ=status.get("type") or {};state=str(typ.get("state") or "").lower();text=" ".join(str(v or "") for v in (typ.get("state"),typ.get("name"),typ.get("detail"),typ.get("shortDetail"),status.get("displayClock"),status.get("period"))).strip().lower()
    if state=="post" or re.search(r"\b(final|final/ot|final/so|complete|completed|postponed|cancelled|canceled)\b",text):return "FINAL"
    if state=="in" or re.search(r"\b(in progress|live|halftime|half time|q[1-4]|[1-9][0-9]?th|period [1-9]|set [1-9]|inning|innings)\b",text):return "LIVE"
    return "UPCOMING"

def _parse_dt(value):
    if not value:return None
    try:return datetime.fromisoformat(str(value).replace("Z","+00:00")).astimezone(timezone.utc)
    except Exception:return None

def _espn_event(name,icon,event):
    start=event.get("date")
    if not start:return None
    comp=(event.get("competitions") or [{}])[0];teams=comp.get("competitors") or []
    home_obj=next((x for x in teams if x.get("homeAway")=="home"),{});away_obj=next((x for x in teams if x.get("homeAway")=="away"),{})
    ht=(home_obj.get("team") or {});at=(away_obj.get("team") or {});home=ht.get("shortDisplayName") or ht.get("displayName") or "";away=at.get("shortDisplayName") or at.get("displayName") or ""
    tag=_state(comp.get("status") or {});e={"league":name,"title":f"{away} @ {home}" if home and away else event.get("name") or event.get("shortName") or name,"start":start,"startUtc":start,"tag":tag,"icon":icon,"source":"espn-live-sweep","providerEventId":f"espn:{event.get('id')}" if event.get("id") else ""}
    if tag=="LIVE":e.update({"status":"LIVE","state":"in"})
    elif tag=="FINAL":e.update({"status":"FINAL","state":"post"})
    else:e.update({"status":"UPCOMING","state":"pre"})
    if home:e["home"]=home
    if away:e["away"]=away
    for side,key in (("home","homeTeamId"),("away","awayTeamId")):
        team=ht if side=="home" else at
        if team.get("id"):e[key]=str(team["id"])
    status=comp.get("status") or {};typ=status.get("type") or {}
    for key in ("shortDetail","detail","displayClock","period"):
        if status.get(key) is not None:e[f"provider_{key}"]=status[key]
        elif typ.get(key) is not None:e[f"provider_{key}"]=typ[key]
    return e

def _merge_key(event):
    league=str(event.get("league") or "").strip().lower();title=str(event.get("title") or "").strip().lower();return league,re.sub(r"[^a-z0-9]+"," ",title).strip()

def _within_window(event,now):
    start=_parse_dt(event.get("startUtc") or event.get("start"))
    if not start or start>now:return False
    sport=str(event.get("sport") or "").lower();league=str(event.get("league") or "").lower();hours=MAX_LIVE_HOURS.get(sport)
    if hours is None:
        for key,value in MAX_LIVE_HOURS.items():
            if key in league:hours=value;break
    return bool(hours and now-start<=timedelta(hours=hours))

def _apply_live_state(event,tag):
    event["tag"]=tag
    if tag=="LIVE":event.update({"status":"LIVE","state":"in"})
    elif tag=="FINAL":event.update({"status":"FINAL","state":"post"})

def main():
    if not FEED.exists():raise SystemExit("ERROR: schedule_feed.json does not exist")
    payload=json.loads(FEED.read_text(encoding="utf-8"));events=[e for e in (payload.get("events") or []) if isinstance(e,dict)];now=datetime.now(timezone.utc)
    results=[]
    with ThreadPoolExecutor(max_workers=min(12,len(ESPN_LEAGUES)+len(NCAA_LEAGUES) or 1)) as pool:
        futures=[pool.submit(_fetch_league,meta) for meta in ESPN_LEAGUES]
        futures.extend(pool.submit(_fetch_ncaa,meta) for meta in NCAA_LEAGUES)
        for future in as_completed(futures):results.append(future.result())
    by_provider={};live_provider=final_provider=fetched_events=0;failed=[];source_groups={}
    for name,raw,error in results:
        if error:failed.append(name);continue
        source_groups[name]="ncaa" if any(m[0]==name for m in NCAA_LEAGUES) else "espn"
        for raw_event in raw:
            if any(m[0]==name for m in NCAA_LEAGUES):
                e=dict(raw_event)
                e.setdefault("startUtc",e.get("start"));e.setdefault("source","espn-ncaa-live-sweep")
                e.setdefault("icon",next((m[3] for m in NCAA_LEAGUES if m[0]==name),"🏆"))
                if e.get("providerEventId") and not str(e["providerEventId"]).startswith("espn:"): e["providerEventId"]=str(e["providerEventId"])
            else:
                meta=next((m for m in ESPN_LEAGUES if m[0]==name),None)
                if not meta:continue
                e=_espn_event(name,meta[3],raw_event)
            if not e:continue
            fetched_events+=1;by_provider[e.get("providerEventId","")]=e
            if e.get("tag")=="LIVE":live_provider+=1
            elif e.get("tag")=="FINAL":final_provider+=1
    changed=0
    for event in events:
        pid=str(event.get("providerEventId") or "");fresh=by_provider.get(pid) if pid else None
        if fresh is None:
            league,title=_merge_key(event);start=_parse_dt(event.get("startUtc") or event.get("start"))
            if start:
                for candidate in by_provider.values():
                    cstart=_parse_dt(candidate.get("startUtc") or candidate.get("start"))
                    if _merge_key(candidate)==(league,title) and cstart and abs(cstart-start)<=timedelta(minutes=20):fresh=candidate;break
        if fresh:
            old=event.get("tag");event.update({k:v for k,v in fresh.items() if v not in (None,"")})
            if old!=event.get("tag"):changed+=1
    existing_provider={str(e.get("providerEventId") or "") for e in events if e.get("providerEventId")};added=0
    for pid,fresh in by_provider.items():
        if not pid or pid in existing_provider or fresh.get("tag") not in {"LIVE","UPCOMING"}:continue
        fresh["sport"]=str(next((m[1] for m in ESPN_LEAGUES if m[0]==fresh.get("league")),next((m[1] for m in NCAA_LEAGUES if m[0]==fresh.get("league")),"other"))).lower()
        fresh["id"]=event_identity(fresh.get("league"),fresh.get("title"),fresh.get("startUtc") or fresh.get("start"),fresh.get("home"),fresh.get("away"));events.append(fresh);added+=1
    inferred=0
    for event in events:
        if event.get("tag")=="FINAL":continue
        if _within_window(event,now) and event.get("tag")!="LIVE":
            _apply_live_state(event,"LIVE");event["liveStateSource"]="bounded-timing-inference";inferred+=1
    events.sort(key=lambda e:str(e.get("startUtc") or e.get("start") or ""));payload["events"]=events;payload["liveSweep"]={"schema":2,"checkedAtUtc":now.isoformat().replace("+00:00","Z"),"leaguesChecked":len(ESPN_LEAGUES)+len(NCAA_LEAGUES),"providerEventsFetched":fetched_events,"providerLive":live_provider,"providerFinal":final_provider,"stateChanges":changed,"eventsAdded":added,"boundedTimingPromotions":inferred,"failedLeagues":sorted(failed),"liveCountAfterSweep":sum(1 for e in events if e.get("tag")=="LIVE"),"providerGroups":source_groups};payload["generatedAt"]=now.isoformat().replace("+00:00","Z");payload["eventCounts"]={}
    for event in events:
        league=event.get("league","Unknown");payload["eventCounts"][league]=payload["eventCounts"].get(league,0)+1
    FEED.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8");print(json.dumps(payload["liveSweep"],indent=2))
if __name__=="__main__":main()
