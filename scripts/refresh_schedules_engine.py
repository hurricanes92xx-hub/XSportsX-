#!/usr/bin/env python3
"""Run the canonical publisher through bounded, rate-limited, season-aware access."""
from __future__ import annotations
import importlib.util
import json
import re
import threading
import time
import urllib.parse
import urllib.request
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
refresh=load('xsportsx_refresh',ROOT/'scripts'/'refresh_schedules.py'); engine=load('xsportsx_schedule_engine_safe',ROOT/'scripts'/'schedule_engine_safe.py'); season=load('xsportsx_season_intelligence',ROOT/'scripts'/'season_intelligence.py')
MAX_CONCURRENT=8; semaphore=threading.BoundedSemaphore(MAX_CONCURRENT); guards={}; guards_lock=threading.Lock()
def guard_for(url):
    host=urllib.parse.urlsplit(url).netloc.lower() or 'unknown'
    with guards_lock: return guards.setdefault(host,engine.SourceGuard())
def guarded_get(url):
    guard=guard_for(url)
    for attempt in range(1,5):
        guard.wait_turn()
        with semaphore:
            try:
                req=urllib.request.Request(url,headers=refresh.HEADERS)
                with urllib.request.urlopen(req,timeout=12) as response: data=response.read()
                guard.success(); return data
            except Exception:
                guard.failure()
                if attempt>=4: raise
                time.sleep(engine.backoff_seconds(attempt))
def previous_root():
    try: return json.loads((ROOT/'data/schedule_feed.json').read_text(encoding='utf-8'))
    except Exception: return {}
PREVIOUS_ROOT=previous_root(); PREVIOUS=PREVIOUS_ROOT.get('events') or []; SEASON_REPORT=[]
def preserved(events,league):
    rows=[e for e in PREVIOUS if e.get('league')==league]; events.extend(rows); return len(rows)
def decision_for(name): return season.analyze(name,PREVIOUS)

def _iso(value):
    if not value: return None
    try: return datetime.fromisoformat(str(value).replace('Z','+00:00')).astimezone(timezone.utc)
    except Exception: return None

def _embedded_json_documents(html):
    """Yield JSON objects from common modern-site application state blocks.

    Many official sports sites are rendered by Next.js/React and expose the
    schedule in application/json or __NEXT_DATA__ rather than JSON-LD. Keep
    this extractor generic so the official source remains authoritative without
    adding a bespoke scraper for every league.
    """
    text=html.decode('utf-8','ignore') if isinstance(html,(bytes,bytearray)) else str(html)
    patterns=[
        r'<script[^>]+type=["\']application/json["\'][^>]*>(.*?)</script>',
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
    ]
    for pattern in patterns:
        for m in re.findall(pattern,text,re.I|re.S):
            try: yield json.loads(m.strip())
            except Exception: continue

def _walk_official_events(value, league, events, seen, now, horizon):
    """Find Event-like records without assuming a provider-specific schema."""
    if isinstance(value,dict):
        name=value.get('name') or value.get('eventName') or value.get('title')
        date=value.get('startDate') or value.get('start') or value.get('startTime') or value.get('date')
        typ=value.get('@type')
        is_event=typ=='Event' or (isinstance(typ,list) and 'Event' in typ)
        # Require both a human-readable title and an ISO-like date before
        # accepting a record. This avoids treating arbitrary page metadata as
        # a schedule event.
        dt=_iso(date)
        if name and dt and (is_event or ('schedule' in str(value).lower() and 'date' in str(value).lower())) and now <= dt <= horizon:
            key=(league,str(name).strip(),dt.isoformat())
            if key not in seen:
                seen.add(key); events.append({'league':league,'title':str(name).strip(),'start':dt.isoformat().replace('+00:00','Z'),'tag':'UPCOMING','icon':'🏆','source':'official'})
        for v in value.values(): _walk_official_events(v,league,events,seen,now,horizon)
    elif isinstance(value,list):
        for v in value: _walk_official_events(v,league,events,seen,now,horizon)

def official_embedded_fallback(events, source):
    name=str(source.get('league') or '').strip(); url=str(source.get('url') or '').strip()
    if not name or not url: return False,0
    try: raw=guarded_get(url)
    except Exception as exc:
        print(f'ERROR official embedded {name}: {exc}'); return False,0
    before=len(events); seen={(e.get('league'),e.get('title'),e.get('start')) for e in events}
    now=datetime.now(timezone.utc)-timedelta(hours=12); horizon=datetime.now(timezone.utc)+timedelta(days=370)
    for doc in _embedded_json_documents(raw): _walk_official_events(doc,name,events,seen,now,horizon)
    return True,len(events)-before

_original_add_official=refresh.add_official_source; _original_add_espn=refresh.add_espn; _original_add_ncaa=refresh.add_ncaa
def season_aware_official(events,source):
    name=str(source.get('league') or '').strip(); d=decision_for(name); SEASON_REPORT.append(d|{'provider':'official'})
    if not name or d['active']:
        ok,n=_original_add_official(events,source)
        # If JSON-LD yielded nothing, inspect the same official page's embedded
        # application state. This is still an official source, not ESPN.
        if ok and n==0:
            eok,en=official_embedded_fallback(events,source)
            if en: return True,en
        return ok,n
    generated=PREVIOUS_ROOT.get('generatedAt',''); last=None
    try: last=datetime.fromisoformat(str(generated).replace('Z','+00:00'))
    except Exception: pass
    age=(datetime.now(timezone.utc)-last).total_seconds()/3600 if last else 999
    if age >= d['probeHours']: return _original_add_official(events,source)
    return True,preserved(events,name)
def season_aware_espn(events,name,sport,league,icon,days):
    d=decision_for(name); SEASON_REPORT.append(d|{'provider':'espn'})
    if not d['active']: return True,preserved(events,name)
    return _original_add_espn(events,name,sport,league,icon,days)
def season_aware_ncaa(events,name,sport,division,icon,days=30):
    d=decision_for(name); SEASON_REPORT.append(d|{'provider':'ncaa'})
    if not d['active']: return True,preserved(events,name)
    return _original_add_ncaa(events,name,sport,division,icon,days)
refresh.get=guarded_get; refresh.add_official_source=season_aware_official; refresh.add_espn=season_aware_espn; refresh.add_ncaa=season_aware_ncaa
refresh.main()
feed=ROOT/'data/schedule_feed.json'
try:
    payload=json.loads(feed.read_text(encoding='utf-8')); payload['seasonIntelligence']={'generatedAt':datetime.now(timezone.utc).isoformat(),'mode':'calendar_plus_observed_activity','providerDecisions':SEASON_REPORT}
    tmp=feed.with_suffix('.tmp'); tmp.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); tmp.replace(feed)
except Exception as exc: print(f'WARNING season intelligence metadata: {exc}')
