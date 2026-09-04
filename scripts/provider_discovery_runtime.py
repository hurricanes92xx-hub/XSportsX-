#!/usr/bin/env python3
"""Runtime bridge for durable web-discovered providers."""
from __future__ import annotations
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from provider_discovery import KNOWLEDGE_FILE, USER_AGENT, MAX_BODY, _extract_events, _safe_url


def _load():
    try:
        value=json.loads(KNOWLEDGE_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value,dict) else {"schema":1,"leagues":{}}
    except Exception:
        return {"schema":1,"leagues":{}}


def _save(value):
    KNOWLEDGE_FILE.parent.mkdir(parents=True,exist_ok=True)
    tmp=KNOWLEDGE_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    tmp.replace(KNOWLEDGE_FILE)


def _probe(rec):
    url=str(rec.get('endpoint') or '')
    if not _safe_url(url): return [],0.0,'unsafe-url'
    started=time.monotonic()
    try:
        req=urllib.request.Request(url,headers={'User-Agent':USER_AGENT,'Accept':'application/json, application/xml, text/xml, text/calendar, text/html;q=0.9,*/*;q=0.5'})
        with urllib.request.urlopen(req,timeout=6) as response:
            body=response.read(MAX_BODY+1)
            if len(body)>MAX_BODY: return [],time.monotonic()-started,'response-too-large'
            ctype=str(response.headers.get('Content-Type',''))
            return _extract_events(body,ctype,str(rec.get('league') or '')),time.monotonic()-started,''
    except Exception as exc:
        return [],time.monotonic()-started,f'{type(exc).__name__}: {exc}'[:220]


def observe(league, limit=5):
    state=_load(); bucket=state.get('leagues',{}).get(league,{})
    records=bucket.get('candidates',[]) or []
    changed=False
    promoted=[]
    for rec in records[:limit]:
        events,latency,error=_probe(rec)
        rec['observations']=int(rec.get('observations',0))+1
        rec['lastLatencyMs']=round(latency*1000,1)
        if events:
            rec['successes']=int(rec.get('successes',0))+1
            rec['failures']=0
            rec['eventCount']=len(events)
            rec['events']=events
            rec['lastSuccess']=datetime.now(timezone.utc).isoformat()
            rec['coverageScore']=min(1.0,len(events)/10.0)
        else:
            rec['failures']=int(rec.get('failures',0))+1
            rec['lastFailure']=datetime.now(timezone.utc).isoformat()
        total=max(1,int(rec.get('successes',0))+int(rec.get('failures',0)))
        rec['reliabilityScore']=round(int(rec.get('successes',0))/total,3)
        # Promotion requires repeated successful observations and healthy coverage.
        if int(rec.get('successes',0))>=2 and float(rec.get('coverageScore',0))>=0.1 and float(rec.get('reliabilityScore',0))>=0.67:
            rec['confidence']=round(min(0.99,0.45+float(rec.get('coverageScore',0))*0.35+float(rec.get('reliabilityScore',0))*0.2),3)
            if rec.get('confidence',0)>=0.65:
                rec['promoted']=True
                promoted.append(rec.get('endpoint'))
        changed=True
    if changed:
        state['updatedAt']=datetime.now(timezone.utc).isoformat()
        state['schema']=1
        _save(state)
    return promoted


def events(league):
    state=_load(); out=[]
    for rec in state.get('leagues',{}).get(league,{}).get('candidates',[]) or []:
        if rec.get('promoted') and float(rec.get('confidence',0))>=0.65:
            for event in rec.get('events',[]) or []:
                item=dict(event); item['source']='discovery'; item['discoveryEndpoint']=rec.get('endpoint'); out.append(item)
    return out


def status(league):
    state=_load(); rows=state.get('leagues',{}).get(league,{}).get('candidates',[]) or []
    return {'discovered':len(rows),'promoted':sum(1 for r in rows if r.get('promoted')),'endpoints':[r.get('endpoint') for r in rows if r.get('promoted')]}
