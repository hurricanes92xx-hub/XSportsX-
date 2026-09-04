#!/usr/bin/env python3
"""Deterministic Sports Brain for schedule truth and LIVE confidence."""
from __future__ import annotations
import argparse,json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
TERMINAL=("final","finished","complete","cancel","postpon","abandon")
LIVE_WORDS=("live","in progress","in-progress","inprogress")

def now_iso(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def parse_time(value):
    try:return datetime.fromisoformat(str(value).replace('Z','+00:00'))
    except (TypeError,ValueError):return None

def max_live_minutes(sport):
    key=str(sport).lower()
    for name,minutes in {"soccer":165,"football":240,"baseball":360,"hockey":240,"basketball":180,"volleyball":180,"tennis":360,"golf":600,"nascar":480,"racing":480,"f1":240,"mma":240}.items():
        if name in key:return minutes
    return 180

def decide(event,now):
    start=parse_time(event.get('startUtc'))
    if not start:return 'UNKNOWN',0.0,'validate_event',["invalid startUtc"]
    text=f"{event.get('status','')} {event.get('state','')}".lower(); elapsed=(now-start).total_seconds()/60.0
    if any(word in text for word in TERMINAL):return 'FINAL',.99,'archive',["terminal provider state"]
    explicit_live=any(word in text for word in LIVE_WORDS); score=event.get('score') is not None or event.get('homeScore') is not None or event.get('awayScore') is not None; clock=bool(event.get('clock') or event.get('period')); source=bool(event.get('sourceUrl') or event.get('youtubeVideoId')); max_minutes=max_live_minutes(event.get('sport',''))
    if explicit_live and elapsed<=max_minutes:
        confidence=.92+(.06 if score or clock else 0); reasons=["explicit live state"]
        if score or clock:reasons.append("independent score/clock evidence agrees")
        if source:reasons.append("playable source metadata is present")
        return 'LIVE',min(confidence,.99),'resolve_or_refresh_source',reasons
    if (score or clock) and -5<=elapsed<=max_minutes:return 'LIVE',.84,'probe_live_state_and_source',["live telemetry without trusted live flag"]
    if elapsed<0:
        if elapsed>=-60:return 'PREGAME',.94,'warm_source' if source else 'discover_event_source_metadata',["inside adaptive pregame window"]
        if elapsed>=-7*24*60:return 'UPCOMING',.91,'refresh_schedule_and_preflight',["within seven-day intelligence horizon"]
        return 'UPCOMING',.75,'defer',["outside active intelligence horizon"]
    if elapsed<=max_minutes:return 'STALE',.88,'refresh_live_evidence',["start time passed without sufficient live evidence"]
    return 'STALE',.94,'reconcile_or_archive',["event exceeded sport-aware live duration without terminal evidence"]

def provider_observations(payload):
    counts=Counter()
    for event in payload.get('events') or []:
        provider=str(event.get('provider') or event.get('sourceProvider') or '')
        if provider:counts[provider]+=1
    for provider,count in (payload.get('sourceRecordCounts') or {}).items():counts[str(provider)]+=int(count or 0)
    return counts

def load_memory(path):
    if not path.exists():return {'schema':1,'updatedAt':None,'events':{},'providers':{},'stats':{}}
    try:
        data=json.loads(path.read_text(encoding='utf-8'));return data if isinstance(data,dict) else {'schema':1,'events':{},'providers':{},'stats':{}}
    except (OSError,json.JSONDecodeError):return {'schema':1,'events':{},'providers':{},'stats':{}}

def analyze(feed_path,memory_path):
    payload=json.loads(feed_path.read_text(encoding='utf-8')); events=payload.get('events') or []; now=datetime.now(timezone.utc); memory=load_memory(memory_path); events_mem=memory.setdefault('events',{}); providers_mem=memory.setdefault('providers',{}); phases=Counter(); actions=Counter(); contradictions=[]; source_gaps=0
    for event in events:
        phase,confidence,action,reasons=decide(event,now); event['intelligencePhase']=phase; event['intelligenceConfidence']=round(confidence,3); event['intelligenceAction']=action; event['intelligenceReasons']=reasons; phases[phase]+=1; actions[action]+=1; eid=str(event.get('id',''))
        if eid:
            prior=events_mem.get(eid,{}); events_mem[eid]={'lastSeen':now_iso(),'phase':phase,'confidence':round(confidence,3),'observations':int(prior.get('observations',0))+1,'liveObservations':int(prior.get('liveObservations',0))+(1 if phase=='LIVE' else 0),'staleObservations':int(prior.get('staleObservations',0))+(1 if phase=='STALE' else 0)}
        provider=str(event.get('provider') or event.get('sourceProvider') or 'unknown'); pm=providers_mem.setdefault(provider,{'observations':0,'live':0,'stale':0,'sourcePresent':0}); pm['observations']+=1; pm['live']+=phase=='LIVE'; pm['stale']+=phase=='STALE'; pm['sourcePresent']+=bool(event.get('sourceUrl') or event.get('youtubeVideoId'))
        if phase=='LIVE' and not (event.get('sourceUrl') or event.get('youtubeVideoId')):source_gaps+=1
        raw_status=f"{event.get('status','')} {event.get('state','')}".lower()
        if any(word in raw_status for word in LIVE_WORDS) and phase!='LIVE':contradictions.append({'eventId':eid,'kind':'live_state_contradiction','decision':phase})
    if len(events_mem)>10000:events_mem=dict(sorted(events_mem.items(),key=lambda item:item[1].get('lastSeen',''),reverse=True)[:10000])
    memory['updatedAt']=now_iso(); memory['stats']={'eventsAnalyzed':len(events),'phases':dict(phases),'actions':dict(actions),'liveWithoutSource':source_gaps,'contradictions':len(contradictions),'providerEventObservations':dict(provider_observations(payload))}
    payload['sportsBrain']={'schema':1,'updatedAt':memory['updatedAt'],'eventsAnalyzed':len(events),'phases':dict(phases),'actions':dict(actions),'liveWithoutSource':source_gaps,'contradictions':contradictions[:100],'memoryEnabled':True}; payload['events']=events; feed_path.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); memory_path.write_text(json.dumps(memory,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); return payload['sportsBrain']

def main():
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest='command',required=True); cmd=sub.add_parser('analyze'); cmd.add_argument('feed'); cmd.add_argument('--memory',default='data/sports_brain_memory.json'); args=parser.parse_args(); print(json.dumps(analyze(Path(args.feed),Path(args.memory)),indent=2))
if __name__=='__main__':main()
