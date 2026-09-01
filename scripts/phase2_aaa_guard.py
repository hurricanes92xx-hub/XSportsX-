#!/usr/bin/env python3
"""Validate AAA coverage after the legacy special repair.

An adapter is successful when authoritative future events are present in the final
feed, whether they were newly inserted or already existed. Never require added > 0.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

FEED=Path('data/schedule_feed.json')
EXPECTED={
    '2026-09-11': 'AAA TripleManía 34 — Night 1 — Las Vegas',
    '2026-09-13': 'AAA TripleManía 34 — Night 2 — Mexico City',
}

def dt(v):
    try:return datetime.fromisoformat(str(v).replace('Z','+00:00')).astimezone(timezone.utc)
    except Exception:return None

p=json.loads(FEED.read_text(encoding='utf-8')); events=p.get('events') or []; now=datetime.now(timezone.utc)
matched=[]
for day,title in EXPECTED.items():
    found=[]
    for e in events:
        if e.get('league')!='AAA Wrestling': continue
        d=dt(e.get('start'))
        if d and d.date().isoformat()==day and d>=now: found.append(e)
    matched.append({'date':day,'expected_title':title,'count':len(found),'events':[{'title':e.get('title'),'start':e.get('start'),'source':e.get('source')} for e in found]})
valid=sum(x['count']>0 for x in matched)
report=p.setdefault('providerRepairReport',{})
previous=report.get('AAA Wrestling') or {}
previous.update({'source':'WWE/AAA official TripleManía announcement','announced':len(EXPECTED),'future_announced':sum(1 for d in EXPECTED if d>=now.date().isoformat()),'existing_or_added_valid_future':valid,'validated':valid>0,'validation_mode':'existing_or_added'})
report['AAA Wrestling']=previous
failures=[x for x in (p.get('officialSourceFailures') or []) if x!='AAA Wrestling'] if valid>0 else list(p.get('officialSourceFailures') or [])
p['officialSourceFailures']=failures
p['phase2RepairReport']=p.get('phase2RepairReport') or {}
p['phase2RepairReport']['AAA Wrestling']=previous
FEED.write_text(json.dumps(p,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps({'league':'AAA Wrestling','matched':matched,'existing_or_added_valid_future':valid,'validated':valid>0},indent=2))
if valid==0: raise SystemExit('AAA Wrestling has no validated future official event in final feed')
