#!/usr/bin/env python3
"""Canonical schedule publisher driven by a league/provider health matrix.

Every league is resolved through primary -> secondary -> tertiary -> cache.
Provider health persists between refreshes and automatically promotes a healthier
provider after repeated failures. No league-specific failure branch is required.
"""
from __future__ import annotations
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import refresh_schedules_legacy as engine
from event_identity import identity_match, merge_event_records, event_identity, normalize_league
from provider_health import build_matrix, provider_order, record, state as health_state
from providers.ncaa import ESPN_FALLBACK as NCAA_ESPN

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "schedule_feed.json"


def _official_map():
    out = {}
    for source in engine.load_official_registry():
        league = str(source.get("league") or "").strip()
        if league: out.setdefault(league, []).append(source)
    return out


def _icons():
    result = {x[0]: x[3] for x in engine.ESPN_LEAGUES}
    result.update({x[0]: x[3] for x in engine.NCAA_LEAGUES})
    result.update({x: "🏎️" for x in engine.NASCAR_SERIES})
    return result


def _dedupe(events):
    priority = {"official": 0, "ncaa": 1, "nascar": 1, "espn": 2, "espn-ncaa": 2, "sportsdb": 3, "fallback": 4, "cache": 5}
    canonical=[]; merges=0; counts={}
    for raw in events:
        candidate=dict(raw); source=candidate.get("source") or "unknown"; counts[source]=counts.get(source,0)+1
        match=None
        for i,existing in enumerate(canonical):
            if identity_match(existing,candidate): match=i; break
        if match is None: canonical.append(candidate); continue
        merges += 1; existing=canonical[match]
        if priority.get(source,9) < priority.get(existing.get("source"),9):
            winner=merge_event_records(candidate,existing); winner["source"]=source; canonical[match]=winner
        else: canonical[match]=merge_event_records(existing,candidate)
    for event in canonical:
        event["id"] = event_identity(event.get("league"), event.get("title"), event.get("start"), event.get("home"), event.get("away"))
    return canonical, merges, counts


def _fetch(provider, league, meta, official, previous):
    icon = meta.get("icon", "🏆"); started=time.monotonic(); error=""
    try:
        if provider == "official":
            events=[]; ok=False
            for source in official.get(league, []):
                source_events=[]; source_ok,n=engine.add_official_source(source_events,source); ok = ok or source_ok; events.extend(source_events)
            return ok, events, error
        if provider == "espn":
            row=meta.get("espn")
            if not row: return False, [], "not configured"
            ok,n_before=engine.add_espn([], league, *row)
            # add_espn's return is intentionally insufficient for the events, so call it once with a list.
            events=[]; ok,n=engine.add_espn(events, league, *row)
            return bool(ok and events), events, error
        if provider == "ncaa":
            row=meta.get("ncaa")
            if not row: return False, [], "not configured"
            events=engine.fetch_ncaa_league(league,*row,horizon_days=30)
            return bool(events), events, error
        if provider == "espn-ncaa":
            mapping=NCAA_ESPN.get(league)
            if not mapping: return False, [], "not configured"
            sport, slug=mapping; events=[]
            start=datetime.now(timezone.utc).date()
            # Reuse the existing ESPN normalizer through the legacy add_espn contract.
            row=(sport,slug,icon,30)
            ok,n=engine.add_espn(events, league, *row)
            for event in events: event["source"]="espn-ncaa"
            return bool(ok and events), events, error
        if provider == "nascar":
            events=engine.fetch_nascar_league(league,horizon_days=370)
            return bool(events), events, error
        if provider == "sportsdb":
            ok,n=engine.add_sportsdb([],league,icon)
            events=[]; ok,n=engine.add_sportsdb(events,league,icon)
            return bool(ok and events), events, error
        if provider == "cache":
            events=[dict(e, source="cache") for e in previous if normalize_league(e.get("league"))==normalize_league(league)]
            return bool(events), events, "cache"
        return False, [], "unknown provider"
    except Exception as exc:
        error=f"{type(exc).__name__}: {exc}"[:300]
        return False, [], error
    finally:
        pass


def main():
    previous={}
    if OUT.exists():
        try: previous=json.loads(OUT.read_text(encoding="utf-8"))
        except Exception: previous={}
    previous_events=previous.get("events") or []
    official=_official_map(); icons=_icons()
    espn={x[0]: x[1:] for x in engine.ESPN_LEAGUES}
    dedicated={x[0]: (x[1],x[2],x[3]) for x in engine.NCAA_LEAGUES}
    dedicated.update({x: ("racing", "", icons.get(x,"🏎️")) for x in engine.NASCAR_SERIES})
    official_leagues=set(official); espn_leagues=set(espn); sportsdb=set(engine.SPORTDB_LEAGUES)
    all_leagues=set(official_leagues)|espn_leagues|set(dedicated)|sportsdb|{"WWE","AEW","TNA"}
    matrix=build_matrix(all_leagues, official_leagues, {k:("ncaa" if k in {x[0] for x in engine.NCAA_LEAGUES} else "nascar") for k in dedicated}, espn_leagues, sportsdb)

    events=[]; failed=[]; attempts={}; promoted={}; source_counts={}; cache_used=[]
    for league in sorted(all_leagues):
        configured=matrix[league]["configured"]
        ordered=provider_order(league,configured)
        matrix[league]["activeOrder"]=ordered
        attempts[league]=[]; selected=None
        meta={"icon":icons.get(league,"🏆"),"espn":espn.get(league),"ncaa":dedicated.get(league)}
        for provider in ordered:
            if provider == "cache":
                ok, got, err=_fetch(provider,league,meta,official,previous_events)
            else:
                ok, got, err=_fetch(provider,league,meta,official,previous_events)
            elapsed=round((time.monotonic()-0),1) if False else 0
            attempts[league].append({"provider":provider,"ok":bool(ok),"events":len(got),"error":err})
            record(league,provider,bool(ok),len(got),0,err)
            if ok and got:
                selected=provider; events.extend(got); break
        if selected is None:
            failed.append(league); continue
        promoted[league]=selected
        if selected == "cache": cache_used.append(league)
        if ordered and selected != ordered[0]:
            matrix[league]["promotedFrom"] = ordered[0]
            matrix[league]["promotedTo"] = selected

    # Wrestling has its own event shape but participates in the same matrix output.
    wrestling=[]; engine.add_wrestling(wrestling); events.extend(wrestling)
    events, merges, source_counts=_dedupe(events)
    events=sorted(events,key=lambda e:e.get("start", ""))
    per={}
    for e in events: per[e.get("league","Unknown")]=per.get(e.get("league","Unknown"),0)+1

    # Cache the last known league only when every live provider for that league failed.
    # This prevents a partial provider from silently replacing good cached coverage.
    payload={
        "schema":9,
        "generatedAt":datetime.now(timezone.utc).isoformat(),
        "refreshHours":6,
        "eventCounts":per,
        "failedSources":failed,
        "providerFailures":[x for x in failed if x in dedicated],
        "sportsDbFallbackSources":[],
        "officialSourceFailures":[],
        "officialSourceCounts":{},
        "identityMergeCount":merges,
        "sourceRecordCounts":source_counts,
        "leagueProviderMatrix":matrix,
        "providerAttempts":attempts,
        "providerPromotions":promoted,
        "cacheRecoveryLeagues":cache_used,
        "events":events,
    }
    tmp=OUT.with_suffix('.tmp'); tmp.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); tmp.replace(OUT)
    print(f"wrote {len(events)} canonical events across {len(per)} leagues; matrix={len(matrix)}; promotions={sum(1 for x in matrix.values() if x.get('promotedTo'))}; cache={len(cache_used)}; identity_merges={merges}")

if __name__=='__main__': main()
