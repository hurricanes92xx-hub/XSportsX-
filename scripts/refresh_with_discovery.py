#!/usr/bin/env python3
"""Run canonical refresh, then season-aware autonomous schedule discovery."""
from __future__ import annotations
import json
from pathlib import Path

import refresh_provider_matrix_v3 as core
import provider_discovery as discovery
import provider_discovery_runtime as runtime
from season_intelligence import analyze

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"schedule_feed.json"

_original_build_matrix=core.build_matrix

def _build_matrix(*args,**kwargs):
    matrix=_original_build_matrix(*args,**kwargs)
    for league in list(matrix):
        promoted=runtime.status(league).get("promoted",0)
        if promoted:
            configured=matrix[league].setdefault("configured",[])
            if "discovery" not in configured: configured.append("discovery")
            matrix[league]["standbyProviders"]=[p for p in matrix[league].get("standbyProviders",[]) if p!="discovery"]
            matrix[league]["discoveredProviderCount"]=promoted
    return matrix

core.build_matrix=_build_matrix
_original_fetch=core.fetch

def _fetch(provider,league,meta,official,previous):
    if provider=="discovery":
        got=runtime.events(league)
        return bool(got),got,"learned web provider" if got else "no promoted discovery provider"
    return _original_fetch(provider,league,meta,official,previous)

core.fetch=_fetch

def _observe_known():
    try:
        state=json.loads(discovery.KNOWLEDGE_FILE.read_text(encoding="utf-8"))
    except Exception:
        state={}
    for league in list((state.get("leagues") or {}).keys()):
        runtime.observe(league,limit=5)

def main():
    _observe_known()
    core.main()
    if not OUT.exists(): return
    payload=json.loads(OUT.read_text(encoding="utf-8"))
    gaps=list(payload.get("noEventLeagues") or [])
    season_states={}
    discovered=0; promoted=0; fallback_attempts=0; discovered_events=[]
    for league in gaps:
        state=analyze(league, payload.get("events") or [])
        season_states[league]=state
        # Only an active/unknown league gets expensive discovery. An inactive
        # league is recorded as OFF_SEASON and revisited on its longer cadence.
        if not state.get("active"):
            continue
        candidates=discovery.discover(league,max_queries=4)
        discovered += len(candidates)
        promoted += sum(1 for c in candidates if c.get("promoted"))
        fallback_attempts += 1
        for candidate in candidates:
            discovered_events.extend(candidate.get("events") or [])
    if discovered_events:
        canonical,merges,_=core.dedupe((payload.get("events") or [])+discovered_events)
        canonical.sort(key=lambda e:e.get("start") or e.get("startUtc") or "")
        payload["events"]=canonical
        payload["identityMergeCount"]=int(payload.get("identityMergeCount",0))+merges
        payload["noEventLeagues"]=[l for l in gaps if not any(e.get("league")==l for e in discovered_events)]
        payload["eventCounts"]={}
        for event in canonical:
            league=event.get("league","Unknown")
            payload["eventCounts"][league]=payload["eventCounts"].get(league,0)+1
    payload["seasonIntelligence"]=season_states
    statuses={league:runtime.status(league) for league in sorted(set(gaps)|set(payload.get("eventCounts",{})))}
    payload["providerDiscovery"]={"enabled":True,"discoveredCandidates":discovered,"promotedProviders":promoted,"fallbackAttempts":fallback_attempts,"leagueStatus":statuses}
    payload["discoveryCount"]=discovered
    payload["discoveredProviders"]=sum(v.get("discovered",0) for v in statuses.values())
    payload["promotedProviders"]=sum(v.get("promoted",0) for v in statuses.values())
    payload["scheduleGapResolution"]={
        "activeGaps":sum(1 for v in season_states.values() if v.get("active")),
        "offSeasonGaps":sum(1 for v in season_states.values() if not v.get("active")),
        "searchedActiveGaps":fallback_attempts,
        "unresolvedAfterDiscovery":len(payload.get("noEventLeagues") or []),
    }
    tmp=OUT.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    tmp.replace(OUT)
    print(f"season-aware discovery: active_gaps={payload['scheduleGapResolution']['activeGaps']}; off_season={payload['scheduleGapResolution']['offSeasonGaps']}; searched={fallback_attempts}; candidates={discovered}; promoted={promoted}")

if __name__=='__main__': main()
