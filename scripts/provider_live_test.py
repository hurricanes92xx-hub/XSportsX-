#!/usr/bin/env python3
from pathlib import Path
import json, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
subprocess.run([sys.executable,str(ROOT/'scripts'/'refresh_schedules.py')],cwd=ROOT,check=True)
data=json.loads((ROOT/'data'/'schedule_feed.json').read_text(encoding='utf-8'))
events=data.get('events') or []
print('=== XSportsX CANONICAL PROVIDER LIVE TEST ===')
print(f"schema={data.get('schema')}")
print(f"canonical_events={len(events)}")
print(f"identity_merges={data.get('identityMergeCount',0)}")
print(f"provider_counts={json.dumps(data.get('sourceRecordCounts',{}),sort_keys=True)}")
def is_live(e):
 s=str(e.get('status','')).lower(); state=str(e.get('state','')).lower(); lifecycle=str(e.get('lifecycle','')).lower()
 return any(x in {s,state,lifecycle} for x in ('live','in_progress','in-progress','live_confirmed')) or any(x in s for x in ('live','in progress'))
live=[e for e in events if is_live(e)]
print(f"live_events={len(live)}")
for e in sorted(live,key=lambda x:(str(x.get('startUtc','')),str(x.get('league','')),str(x.get('title','')))):
 print(json.dumps({k:e.get(k) for k in ('id','sport','league','title','home','away','startUtc','status','state','lifecycle','source','tag','broadcast') if e.get(k) is not None},sort_keys=True))
