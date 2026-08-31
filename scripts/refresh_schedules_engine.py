#!/usr/bin/env python3
"""Run the canonical publisher through bounded, rate-limited, season-aware access."""
from __future__ import annotations
import importlib.util
import json
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path); module=importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(module); return module
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
_original_add_official=refresh.add_official_source; _original_add_espn=refresh.add_espn; _original_add_ncaa=refresh.add_ncaa
def season_aware_official(events,source):
    name=str(source.get('league') or '').strip(); d=decision_for(name); SEASON_REPORT.append(d|{'provider':'official'})
    if not name or d['active']: return _original_add_official(events,source)
    # Inactive official sources are probed once per 24h. This preserves the last
    # good calendar while preventing dozens of offseason pages from being fetched
    # on every 30-minute workflow tick.
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
