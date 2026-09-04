#!/usr/bin/env python3
"""Canonical schedule refresh with provider health separated from empty schedules.

The refresh must sample every configured provider before canonicalization.  The
health-ranked provider remains the preferred record, but secondary providers are
kept as evidence so cross-provider identity and metadata merging can operate.
"""
from __future__ import annotations
import json,time
from datetime import datetime,timezone
from pathlib import Path
import refresh_schedules_legacy as engine
from event_identity import identity_match,merge_event_records,event_identity,normalize_league
from provider_health import build_matrix,provider_order,record
from providers.ncaa import ESPN_FALLBACK as NCAA_ESPN
from providers.expanded import fetch as fetch_expanded

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"schedule_feed.json"
_WRESTLING_CACHE=None


def official_map():
    out={}
    for source in engine.load_official_registry():
        league=str(source.get("league") or "").strip()
        if league: out.setdefault(league,[]).append(source)
    return out


def icon_map():
    out={x[0]:x[3] for x in engine.ESPN_LEAGUES}
    out.update({x[0]:x[3] for x in engine.NCAA_LEAGUES})
    out.update({x:"🏎️" for x in engine.NASCAR_SERIES})
    out.update({"WWE":"🏆","AEW":"🤼","TNA":"🤼","Esports":"🎮"})
    return out


def source_priority(source):
    return {"mlb-official":0,"nhl-official":0,"official":0,
            "ncaa":1,"nascar":1,"wrestling":1,"sportradar":1,
            "sportsdataio":1,"sportmonks":1,"cfbd":1,"pandascore":1,
            "espn":2,"espn-ncaa":2,"sportsdb":3,"fallback":4,"cache":5}.get(source,9)


def dedupe(events):
    canonical=[]
    merges=0
    counts={}
    for raw in events:
        candidate=dict(raw)
        source=candidate.get("source") or "unknown"
        counts[source]=counts.get(source,0)+1
        match=next((i for i,e in enumerate(canonical) if identity_match(e,candidate)),None)
        if match is None:
            canonical.append(candidate)
            continue
        merges+=1
        existing=canonical[match]
        existing_source=existing.get("source") or "unknown"
        if source_priority(source)<source_priority(existing_source):
            winner=merge_event_records(candidate,existing)
            winner["source"]=source
            canonical[match]=winner
        else:
            canonical[match]=merge_event_records(existing,candidate)
    for event in canonical:
        event["id"]=event_identity(event.get("league"),event.get("title"),event.get("start"),event.get("home"),event.get("away"))
    return canonical,merges,counts


def fetch(provider,league,meta,official,previous):
    global _WRESTLING_CACHE
    try:
        if provider in {"sportradar","sportsdataio","sportmonks","cfbd","mlb-official","nhl-official","pandascore"}:
            return fetch_expanded(provider,league,meta["icon"])
        if provider=="official":
            events=[]
            ok=False
            for source in official.get(league,[]):
                part=[]
                source_ok,_=engine.add_official_source(part,source)
                ok=ok or source_ok
                events.extend(part)
            return ok,events,""
        if provider=="espn":
            row=meta.get("espn")
            if not row:return False,[],"not configured"
            events=[]
            ok,_=engine.add_espn(events,league,*row)
            for event in events:event.setdefault("source","espn")
            return bool(ok),events,""
        if provider=="ncaa":
            row=meta.get("ncaa")
            if not row:return False,[],"not configured"
            events=engine.fetch_ncaa_league(league,*row,horizon_days=30)
            for event in events:event.setdefault("source","ncaa")
            return True,events,""
        if provider=="espn-ncaa":
            mapping=NCAA_ESPN.get(league)
            if not mapping:return False,[],"not configured"
            events=[]
            ok,_=engine.add_espn(events,league,mapping[0],mapping[1],meta["icon"],30)
            for event in events:event["source"]="espn-ncaa"
            return bool(ok),events,""
        if provider=="nascar":
            events=engine.fetch_nascar_league(league,horizon_days=370)
            for event in events:event.setdefault("source","nascar")
            return True,events,""
        if provider=="wrestling":
            if _WRESTLING_CACHE is None:
                _WRESTLING_CACHE=[]
                engine.add_wrestling(_WRESTLING_CACHE)
            events=[dict(event,source="wrestling") for event in _WRESTLING_CACHE if event.get("league")==league]
            return True,events,""
        if provider=="sportsdb":
            events=[]
            ok,_=engine.add_sportsdb(events,league,meta["icon"])
            for event in events:event.setdefault("source","sportsdb")
            return bool(ok),events,""
        if provider=="cache":
            events=[dict(event,source="cache") for event in previous if normalize_league(event.get("league"))==normalize_league(league)]
            return bool(events),events,"cache"
        return False,[],"unknown provider"
    except Exception as exc:
        return False,[],f"{type(exc).__name__}: {exc}"[:300]


def main():
    previous={}
    if OUT.exists():
        try: previous=json.loads(OUT.read_text(encoding="utf-8"))
        except Exception: previous={}
    previous_events=previous.get("events") or []
    officials=official_map()
    icons=icon_map()
    espn={x[0]:x[1:] for x in engine.ESPN_LEAGUES}
    ncaa={x[0]:x[1:] for x in engine.NCAA_LEAGUES}
    dedicated_names=set(ncaa)|set(engine.NASCAR_SERIES)|{"WWE","AEW","TNA"}
    official_names=set(officials)
    sportsdb_names=set(engine.SPORTDB_LEAGUES)
    all_leagues=official_names|set(espn)|dedicated_names|sportsdb_names|{"Esports"}
    dedicated={name:("ncaa" if name in ncaa else "nascar" if name in engine.NASCAR_SERIES else "wrestling") for name in dedicated_names}
    matrix=build_matrix(all_leagues,official_names,dedicated,set(espn),sportsdb_names)

    events=[]
    failures=[]
    no_event_leagues=[]
    attempts={}
    promotions={}
    cache_recovery=[]
    overlap_leagues=[]
    overlap_records=0

    for league in sorted(all_leagues):
        ordered=provider_order(league,matrix[league]["configured"])
        matrix[league]["activeOrder"]=ordered
        attempts[league]=[]
        meta={"icon":icons.get(league,"🏆"),"espn":espn.get(league),"ncaa":ncaa.get(league)}
        successful=[]

        # Do not short-circuit after the first provider.  The primary provider is
        # still first in the merge priority, while fallback providers provide
        # coverage, alternate IDs/names, and metadata for canonicalization.
        for provider in ordered:
            started=time.monotonic()
            ok,got,error=fetch(provider,league,meta,officials,previous_events)
            latency=round((time.monotonic()-started)*1000,1)
            attempts[league].append({"provider":provider,"ok":ok,"events":len(got),"latencyMs":latency,"error":error})
            record(league,provider,ok,len(got),latency,error)
            if ok and got:
                successful.append((provider,got))

        if not successful:
            started=time.monotonic()
            cache_ok,cache_events,cache_error=fetch("cache",league,meta,officials,previous_events)
            latency=round((time.monotonic()-started)*1000,1)
            attempts[league].append({"provider":"cache","ok":cache_ok,"events":len(cache_events),"latencyMs":latency,"error":cache_error})
            record(league,"cache",cache_ok,len(cache_events),latency,cache_error)
            if cache_ok and cache_events:
                successful=[("cache",cache_events)]
                cache_recovery.append(league)

        if not successful:
            failures.append(league)
            continue

        selected=successful[0][0]
        if ordered and selected!=ordered[0]:
            matrix[league]["promotedFrom"]=ordered[0]
            matrix[league]["promotedTo"]=selected
            promotions[league]=selected
        if len(successful)>1:
            overlap_leagues.append(league)
            overlap_records += sum(len(records) for _,records in successful[1:])

        for provider,records in successful:
            for event in records:event.setdefault("source",provider)
            events.extend(records)

    events,merges,source_counts=dedupe(events)
    events.sort(key=lambda e:e.get("start") or e.get("startUtc") or "")
    per={}
    for event in events:
        league=event.get("league","Unknown")
        per[league]=per.get(league,0)+1

    payload={
        "schema":11,
        "generatedAt":datetime.now(timezone.utc).isoformat(),
        "refreshHours":6,
        "eventCounts":per,
        "failedSources":failures,
        "providerFailures":failures,
        "noEventLeagues":no_event_leagues,
        "sportsDbFallbackSources":[],
        "officialSourceFailures":[],
        "officialSourceCounts":{},
        "identityMergeCount":merges,
        "sourceRecordCounts":source_counts,
        "shadowProviderRecordCounts":source_counts,
        "providerOverlapLeagues":overlap_leagues,
        "providerOverlapRecordCount":overlap_records,
        "leagueProviderMatrix":matrix,
        "providerAttempts":attempts,
        "providerPromotions":promotions,
        "cacheRecoveryLeagues":cache_recovery,
        "events":events,
    }
    tmp=OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    tmp.replace(OUT)
    print(f"wrote {len(events)} canonical events across {len(per)} leagues; failures={len(failures)}; no_events={len(no_event_leagues)}; promotions={len(promotions)}; cache={len(cache_recovery)}; identity_merges={merges}; overlap_leagues={len(overlap_leagues)}")

if __name__=="__main__":main()
