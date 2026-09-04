#!/usr/bin/env python3
"""Canonical schedule refresh with provider health separated from empty schedules."""
from __future__ import annotations
import json,time
from datetime import datetime,timezone
from pathlib import Path
import refresh_schedules_legacy as engine
from event_identity import identity_match,merge_event_records,event_identity,normalize_league
from provider_health import build_matrix,provider_order,record
from providers.ncaa import ESPN_FALLBACK as NCAA_ESPN
from providers.expanded import fetch as fetch_expanded
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/"data"/"schedule_feed.json"
_WRESTLING_CACHE=None

def official_map():
    out={}
    for source in engine.load_official_registry():
        league=str(source.get("league") or "").strip()
        if league:out.setdefault(league,[]).append(source)
    return out

def icon_map():
    out={x[0]:x[3] for x in engine.ESPN_LEAGUES};out.update({x[0]:x[3] for x in engine.NCAA_LEAGUES});out.update({x:"🏎️" for x in engine.NASCAR_SERIES});out.update({"WWE":"🏆","AEW":"🤼","TNA":"🤼","Esports":"🎮"});return out

def dedupe(events):
    priority={"mlb-official":0,"nhl-official":0,"official":0,"ncaa":1,"nascar":1,"wrestling":1,"sportradar":1,"sportsdataio":1,"sportmonks":1,"cfbd":1,"pandascore":1,"espn":2,"espn-ncaa":2,"sportsdb":3,"fallback":4,"cache":5}
    canonical=[];merges=0;counts={}
    for raw in events:
        candidate=dict(raw);source=candidate.get("source") or "unknown";counts[source]=counts.get(source,0)+1
        match=next((i for i,e in enumerate(canonical) if identity_match(e,candidate)),None)
        if match is None:canonical.append(candidate);continue
        merges+=1;existing=canonical[match]
        if priority.get(source,9)<priority.get(existing.get("source"),9):
            winner=merge_event_records(candidate,existing);winner["source"]=source;canonical[match]=winner
        else:canonical[match]=merge_event_records(existing,candidate)
    for e in canonical:e["id"]=event_identity(e.get("league"),e.get("title"),e.get("start"),e.get("home"),e.get("away"))
    return canonical,merges,counts

def fetch(provider,league,meta,official,previous):
    global _WRESTLING_CACHE
    try:
        if provider in {"sportradar","sportsdataio","sportmonks","cfbd","mlb-official","nhl-official","pandascore"}:
            return fetch_expanded(provider,league,meta["icon"])
        if provider=="official":
            events=[];ok=False
            for source in official.get(league,[]):
                part=[];source_ok,_=engine.add_official_source(part,source);ok=ok or source_ok;events.extend(part)
            return ok,events,""
        if provider=="espn":
            row=meta.get("espn")
            if not row:return False,[],"not configured"
            events=[];ok,_=engine.add_espn(events,league,*row);return bool(ok),events,""
        if provider=="ncaa":
            row=meta.get("ncaa")
            if not row:return False,[],"not configured"
            events=engine.fetch_ncaa_league(league,*row,horizon_days=30);return True,events,""
        if provider=="espn-ncaa":
            mapping=NCAA_ESPN.get(league)
            if not mapping:return False,[],"not configured"
            events=[];ok,_=engine.add_espn(events,league,mapping[0],mapping[1],meta["icon"],30)
            for e in events:e["source"]="espn-ncaa"
            return bool(ok),events,""
        if provider=="nascar":
            events=engine.fetch_nascar_league(league,horizon_days=370);return True,events,""
        if provider=="wrestling":
            if _WRESTLING_CACHE is None:_WRESTLING_CACHE=[];engine.add_wrestling(_WRESTLING_CACHE)
            events=[dict(e,source="wrestling") for e in _WRESTLING_CACHE if e.get("league")==league]
            return True,events,""
        if provider=="sportsdb":
            events=[];ok,_=engine.add_sportsdb(events,league,meta["icon"]);return bool(ok),events,""
        if provider=="cache":
            events=[dict(e,source="cache") for e in previous if normalize_league(e.get("league"))==normalize_league(league)]
            return bool(events),events,"cache"
        return False,[],"unknown provider"
    except Exception as exc:return False,[],f"{type(exc).__name__}: {exc}"[:300]

def main():
    previous={}
    if OUT.exists():
        try:previous=json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:previous={}
    previous_events=previous.get("events") or [];officials=official_map();icons=icon_map();espn={x[0]:x[1:] for x in engine.ESPN_LEAGUES};ncaa={x[0]:x[1:] for x in engine.NCAA_LEAGUES}
    dedicated_names=set(ncaa)|set(engine.NASCAR_SERIES)|{"WWE","AEW","TNA"};official_names=set(officials);sportsdb_names=set(engine.SPORTDB_LEAGUES);all_leagues=official_names|set(espn)|dedicated_names|sportsdb_names|{"Esports"}
    dedicated={name:("ncaa" if name in ncaa else "nascar" if name in engine.NASCAR_SERIES else "wrestling") for name in dedicated_names}
    matrix=build_matrix(all_leagues,official_names,dedicated,set(espn),sportsdb_names)
    events=[];failures=[];no_event_leagues=[];attempts={};promotions={};cache_recovery=[]
    for league in sorted(all_leagues):
        ordered=provider_order(league,matrix[league]["configured"]);matrix[league]["activeOrder"]=ordered;attempts[league]=[];selected=None;meta={"icon":icons.get(league,"🏆"),"espn":espn.get(league),"ncaa":ncaa.get(league)}
        for provider in ordered+["cache"]:
            started=time.monotonic();ok,got,error=fetch(provider,league,meta,officials,previous_events);latency=round((time.monotonic()-started)*1000,1)
            attempts[league].append({"provider":provider,"ok":ok,"events":len(got),"latencyMs":latency,"error":error});record(league,provider,ok,len(got),latency,error)
            if ok:
                selected=provider
                if got:events.extend(got)
                break
        if selected is None:failures.append(league);continue
        if not any(a["events"] for a in attempts[league] if a["ok"]):no_event_leagues.append(league)
        if selected=="cache":cache_recovery.append(league)
        if ordered and selected!=ordered[0]:matrix[league]["promotedFrom"]=ordered[0];matrix[league]["promotedTo"]=selected;promotions[league]=selected
    events,merges,source_counts=dedupe(events);events.sort(key=lambda e:e.get("start",""));per={}
    for e in events:per[e.get("league","Unknown")]=per.get(e.get("league","Unknown"),0)+1
    payload={"schema":11,"generatedAt":datetime.now(timezone.utc).isoformat(),"refreshHours":6,"eventCounts":per,"failedSources":failures,"providerFailures":failures,"noEventLeagues":no_event_leagues,"sportsDbFallbackSources":[],"officialSourceFailures":[],"officialSourceCounts":{},"identityMergeCount":merges,"sourceRecordCounts":source_counts,"leagueProviderMatrix":matrix,"providerAttempts":attempts,"providerPromotions":promotions,"cacheRecoveryLeagues":cache_recovery,"events":events}
    tmp=OUT.with_suffix(".tmp");tmp.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8");tmp.replace(OUT)
    print(f"wrote {len(events)} canonical events across {len(per)} leagues; failures={len(failures)}; no_events={len(no_event_leagues)}; promotions={len(promotions)}; cache={len(cache_recovery)}; identity_merges={merges}")
if __name__=="__main__":main()
