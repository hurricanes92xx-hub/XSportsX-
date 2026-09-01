#!/usr/bin/env python3
"""Repair NASCAR Cup from the shared official NASCAR race cache."""
from __future__ import annotations
import json, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; FEED=ROOT/'data'/'schedule_feed.json'
NOW=datetime.now(timezone.utc); HORIZON=NOW+timedelta(days=370)
HEADERS={'User-Agent':'XSportsX-Schedule/5.6','Accept':'application/json,text/plain,*/*'}

def get_json(url):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=30) as r:
        return json.loads(r.read().decode('utf-8','ignore'))

def iso(v):
    if not v:return None
    s=str(v).strip()
    for x in (s,s.replace('Z','+00:00'),s.replace('z','+00:00')):
        try:return datetime.fromisoformat(x).astimezone(timezone.utc).isoformat().replace('+00:00','Z')
        except ValueError:pass
    return None

def rows_for_cup(root):
    if not isinstance(root,dict): return []
    for key in ('Series_1','series_1','1'):
        value=root.get(key)
        if isinstance(value,list): return [x for x in value if isinstance(x,dict)]
        if isinstance(value,dict):
            for k in ('races','schedule','events'):
                if isinstance(value.get(k),list): return [x for x in value[k] if isinstance(x,dict)]
    return []

p=json.loads(FEED.read_text(encoding='utf-8')); events=p.get('events') or []
existing={(e.get('league'),e.get('title'),e.get('start')) for e in events}
root=get_json(f'https://cf.nascar.com/cacher/{NOW.year}/race_list_basic.json')
rows=rows_for_cup(root); added=0; current=0
for r in rows:
    start=iso(r.get('date_scheduled') or r.get('tunein_date') or r.get('race_date'))
    if not start: continue
    dt=datetime.fromisoformat(start.replace('Z','+00:00'))
    if not NOW-timedelta(hours=12) <= dt <= HORIZON: continue
    race=str(r.get('race_name') or 'NASCAR Cup').strip(); track=str(r.get('track_name') or '').strip()
    title=' — '.join(x for x in (race,track) if x) or 'NASCAR Cup'; key=('NASCAR Cup',title,start)
    if key in existing:
        current+=1; continue
    events.append({'league':'NASCAR Cup','title':title,'start':start,'tag':'LIVE' if dt<=NOW else 'UPCOMING','icon':'🏁','source':'official_api','sourceDetail':'NASCAR official shared CF race_list_basic'}); existing.add(key); added+=1; current+=1
p['events']=events
p.setdefault('officialApiAdapterReport',{}).setdefault('nascar',{})['NASCAR Cup']=f'official_shared_cache:{len(rows)}; current_future:{current}; added:{added}'
if current:
    p['officialSourceFailures']=[x for x in (p.get('officialSourceFailures') or []) if x!='NASCAR Cup']
    print(f'REPAIRED NASCAR Cup: shared cache rows={len(rows)}, current_future={current}, added={added}')
else:
    raise RuntimeError(f'NASCAR Cup still has no current/future races; shared cache rows={len(rows)}')
p['eventCounts']={k:sum(1 for e in events if e.get('league')==k) for k in sorted({e.get('league') for e in events if e.get('league')})}
FEED.write_text(json.dumps(p,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
