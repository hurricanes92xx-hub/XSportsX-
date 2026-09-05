#!/usr/bin/env python3
"""Fast, provider-first live-state reconciliation across every configured league."""
from __future__ import annotations
import json,re,urllib.request
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone,timedelta
from pathlib import Path
from refresh_schedules_legacy import ESPN_LEAGUES
from providers.ncaa import NCAA_LEAGUES,_fetch_espn_day,_fetch_current_day,_normalize
from providers.fivb import fetch as fetch_fivb
from providers.free import _espn_cricket,openf1
from event_identity import event_identity
ROOT=Path(__file__).resolve().parents[1]
FEED=ROOT/"data"/"schedule_feed.json"
HEADERS={"User-Agent":"XSportsX-LiveSweep/1.5","Accept":"application/json, */*","Accept-Language":"en-US,en;q=0.9"}

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
    name,sport,division,icon=meta;day=datetime.now(timezone.utc).date();records=[];errors=[]
    try:
        root=_fetch_current_day(sport,division,day)
        if root:
            for game in __import__('providers.ncaa',fromlist=['_walk_games'])._walk_games(root):
                event=_normalize(game,name,icon)
                if event:records.append(event)
    except Exception as exc:errors.append(f"primary:{exc}")
    try:records.extend(_fetch_espn_day(name,day))
    except Exception as exc:errors.append(f"espn:{exc}")
    seen=set();out=[]
    for event in records:
        key=(str(event.get('away') or '').lower(),str(event.get('home') or '').lower(),str(event.get('start') or event.get('startUtc') or ''))
        if key in seen:continue
        seen.add(key);out.append(event)
    return name,out,"; ".join(errors) if errors and not out else None

def _fetch_dedicated(item):
    name,kind,icon=item
    try:
        if kind=="fivb":
            ok,events,error=fetch_fivb(name,icon);return name,events,error if not ok else None
        if kind=="cricket":
            ok,events=_espn_cricket(name,icon);return name,events,None if ok else "ESPN cricket endpoint failed"
        if kind=="f1":
            ok,events,error=openf1(name,icon);return name,events,error if not ok else None
    except Exception as exc:return name,[],f"{type(exc).__name__}: {exc}"
    return name,[],"unsupported dedicated provider"

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

def _normalize_dedicated(name,raw):
    e=dict(raw);e.setdefault("startUtc",e.get("start"));e.setdefault("source",f"{name.lower().replace(' ','-')}-live-provider")
    tag=str(e.get("tag") or e.get("status") or "UPCOMING").upper()
    if tag=="LIVE":e.update({"status":"LIVE","state":"in"})
    elif tag=="FINAL":e.update({"status":"FINAL","state":"post"})
    else:e.update({"status":"UPCOMING","state":"pre"})
    return e

def _merge_key(event):
    league=str(event.get("league") or "").strip().lower();title=str(event.get("title") or "").strip().lower();return league,re.sub(r"[^a-z0-9]+"," ",title).strip()

def _league_key(value):
    return re.sub(r"[^a-z0-9]+"," ",str(value or "").strip().lower()).strip()

def _apply_provider_time_guard(event,now):
    """Never expose a provider LIVE state for an event clearly in the future."""
    if str(event.get("tag") or "").upper()!="LIVE":return event,False
    start=_parse_dt(event.get("startUtc") or event.get("start"))
    if start and start>now+timedelta(minutes=2):
        event.update({"tag":"UPCOMING","status":"UPCOMING","state":"pre"})
        event["liveStateRejectedReason"]="provider-live-starts-too-far-in-future"
        return event,True
    return event,False

def _mark_live_evidence(event,checked_at):
    if str(event.get("tag") or "").upper()=="LIVE":
        event["liveEvidence"]={"source":str(event.get("source") or "provider"),"providerEventId":str(event.get("providerEventId") or ""),"providerState":"LIVE","checkedAtUtc":checked_at}
    else:event.pop("liveEvidence",None)
    return event

def main():
    if not FEED.exists():raise SystemExit("ERROR: schedule_feed.json does not exist")
    payload=json.loads(FEED.read_text(encoding="utf-8"));events=[e for e in (payload.get("events") or []) if isinstance(e,dict)];now=datetime.now(timezone.utc);checked_at=now.isoformat().replace("+00:00","Z")
    dedicated=[("FIVB Men","fivb","🏐"),("FIVB Women","fivb","🏐"),("ICC T20","cricket","🏏"),("IPL","cricket","🏏"),("F1","f1","🏎️")]
    results=[]
    with ThreadPoolExecutor(max_workers=min(16,len(ESPN_LEAGUES)+len(NCAA_LEAGUES)+len(dedicated) or 1)) as pool:
        futures=[pool.submit(_fetch_league,meta) for meta in ESPN_LEAGUES];futures.extend(pool.submit(_fetch_ncaa,meta) for meta in NCAA_LEAGUES);futures.extend(pool.submit(_fetch_dedicated,item) for item in dedicated)
        for future in as_completed(futures):results.append(future.result())
    by_provider={};live_provider=final_provider=fetched_events=0;failed=[];source_groups={};successful_leagues=set();future_live_rejected=0
    dedicated_names={x[0] for x in dedicated};ncaa_meta={m[0]:m for m in NCAA_LEAGUES};espn_meta={m[0]:m for m in ESPN_LEAGUES}
    for name,raw,error in results:
        if error:failed.append(name);continue
        successful_leagues.add(_league_key(name));source_groups[name]="ncaa" if name in ncaa_meta else "dedicated" if name in dedicated_names else "espn"
        for raw_event in raw:
            if name in ncaa_meta:
                e=dict(raw_event);e.setdefault("startUtc",e.get("start"));e.setdefault("source","ncaa-live-sweep");e.setdefault("icon",ncaa_meta[name][3]);e.setdefault("sport",str(ncaa_meta[name][1]).lower());tag=str(e.get("tag") or e.get("status") or "UPCOMING").upper();e.update({"status":"LIVE","state":"in"} if tag=="LIVE" else {"status":"FINAL","state":"post"} if tag=="FINAL" else {"status":"UPCOMING","state":"pre"});e["tag"]=tag
            elif name in dedicated_names:e=_normalize_dedicated(name,raw_event);e.setdefault("sport", "racing" if name=="F1" else "volleyball" if name.startswith("FIVB") else "cricket")
            else:
                meta=espn_meta.get(name)
                if not meta:continue
                e=_espn_event(name,meta[3],raw_event);e["sport"]=str(meta[1]).lower() if e else "other"
            if not e:continue
            e,rejected=_apply_provider_time_guard(e,now);future_live_rejected+=1 if rejected else 0;fetched_events+=1;pid=str(e.get("providerEventId") or f"{e.get('source')}:{e.get('league')}:{e.get('title')}:{e.get('startUtc')}");by_provider[pid]=e
            if e.get("tag")=="LIVE":live_provider+=1
            elif e.get("tag")=="FINAL":final_provider+=1
    changed=stale_live_demoted=0
    for event in events:
        pid=str(event.get("providerEventId") or "");fresh=by_provider.get(pid) if pid else None
        if fresh is None:
            league,title=_merge_key(event);start=_parse_dt(event.get("startUtc") or event.get("start"))
            for candidate in by_provider.values():
                cstart=_parse_dt(candidate.get("startUtc") or candidate.get("start"))
                if _merge_key(candidate)==(league,title) and cstart and start and abs(cstart-start)<=timedelta(minutes=20):fresh=candidate;break
        if fresh:
            old=(event.get("tag"),event.get("status"),event.get("state"));event.update({k:v for k,v in fresh.items() if v not in (None,"")});_mark_live_evidence(event,checked_at)
            if old!=(event.get("tag"),event.get("status"),event.get("state")):changed+=1
        elif _league_key(event.get("league")) in successful_leagues and str(event.get("tag") or event.get("status") or "").upper()=="LIVE":
            event.update({"tag":"UPCOMING","status":"UPCOMING","state":"pre"});event.pop("liveEvidence",None);event["liveStateRejectedReason"]="provider-checked-not-live";stale_live_demoted+=1;changed+=1
    existing_provider={str(e.get("providerEventId") or "") for e in events if e.get("providerEventId")};added=0
    for pid,fresh in by_provider.items():
        if not pid or pid in existing_provider or fresh.get("tag") not in {"LIVE","UPCOMING"}:continue
        fresh["sport"]=str(fresh.get("sport") or "other").lower();fresh["id"]=event_identity(fresh.get("league"),fresh.get("title"),fresh.get("startUtc") or fresh.get("start"),fresh.get("home"),fresh.get("away"));_mark_live_evidence(fresh,checked_at);events.append(fresh);added+=1
    events.sort(key=lambda e:str(e.get("startUtc") or e.get("start") or ""));payload["events"]=events
    payload["liveSweep"]={"schema":5,"checkedAtUtc":checked_at,"leaguesChecked":len(ESPN_LEAGUES)+len(NCAA_LEAGUES)+len(dedicated),"providerEventsFetched":fetched_events,"providerLive":live_provider,"providerFinal":final_provider,"stateChanges":changed,"eventsAdded":added,"boundedTimingPromotions":0,"staleLiveDemoted":stale_live_demoted,"futureLiveRejected":future_live_rejected,"failedLeagues":sorted(set(failed)),"liveCountAfterSweep":sum(1 for e in events if str(e.get("tag") or "").upper()=="LIVE"),"providerGroups":source_groups,"liveStatePolicy":"provider-authoritative-strict-reconciliation","endpoints":{"espn":"site.api.espn.com + site.web.api.espn.com","ncaa":"ncaa-api.henrygd.me + ESPN fallback","fivb":"fivb.org VIS","cricket":"ESPN personalized scoreboard","f1":"OpenF1"}}
    payload["generatedAt"]=checked_at;payload["eventCounts"]={}
    for event in events:
        league=event.get("league","Unknown");payload["eventCounts"][league]=payload["eventCounts"].get(league,0)+1
    FEED.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8");print(json.dumps(payload["liveSweep"],indent=2))

if __name__=="__main__":main()
