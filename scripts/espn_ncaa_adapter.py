#!/usr/bin/env python3
"""ESPN-backed NCAA schedule fallback for sports where NCAA public feeds are unavailable."""
from __future__ import annotations
import json
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FEED=ROOT/'data'/'schedule_feed.json'
HEADERS={'User-Agent':'Mozilla/5.0 XSportsX-Schedule/5.5','Accept':'application/json,text/plain,*/*','Accept-Language':'en-US,en;q=0.9'}
NOW=datetime.now(timezone.utc); HORIZON=NOW+timedelta(days=370)
SPORTS=[
 ('NCAA FB','football','college-football','🏈'),
 ('NCAA BB','basketball','mens-college-basketball','🏀'),
 ('NCAA WBB','basketball','womens-college-basketball','🏀'),
 ('NCAA Baseball','baseball','college-baseball','⚾'),
 ('NCAA Softball','softball','college-softball','🥎'),
 ("NCAA Men's Soccer",'soccer','usa.ncaa.1','⚽'),
 ("NCAA Women's Soccer",'soccer','usa.ncaa.w.1','⚽'),
 ("NCAA Men's Volleyball",'volleyball','mens-college-volleyball','🏐'),
 ("NCAA Women's Volleyball",'volleyball','womens-college-volleyball','🏐'),
 ("NCAA Men's Hockey",'hockey','mens-college-hockey','🏒'),
 ("NCAA Women's Hockey",'hockey','womens-college-hockey','🏒'),
 ("NCAA Women's Field Hockey",'fieldhockey','ncaa-field-hockey','🏑'),
]

def get_json(url):
 req=urllib.request.Request(url,headers=HEADERS)
 with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read().decode('utf-8','ignore'))

def iso(v):
 if not v:return None
 try:return datetime.fromisoformat(str(v).replace('Z','+00:00')).astimezone(timezone.utc).isoformat().replace('+00:00','Z')
 except ValueError:return None

def name(team):
 if not isinstance(team,dict):return ''
 t=team.get('team') or team
 for k in ('displayName','shortDisplayName','name','abbreviation'):
  if isinstance(t.get(k),str) and t[k].strip():return t[k].strip()
 return ''

def add_events(events,report):
 existing={(e.get('league'),e.get('title'),e.get('start')) for e in events}
 start=NOW.date()
 for league,sport,slug,icon in SPORTS:
  added=0;raw=0;errors=0;seen=set();cursor=start
  while cursor<=HORIZON.date():
   end=min(cursor+timedelta(days=29),HORIZON.date())
   url=f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/scoreboard?dates={cursor:%Y%m%d}-{end:%Y%m%d}&limit=1000'
   try:root=get_json(url)
   except Exception:
    errors+=1;cursor=end+timedelta(days=1);continue
   for g in root.get('events') or []:
    raw+=1;gid=str(g.get('id') or '')
    if gid in seen:continue
    seen.add(gid);dt=iso(g.get('date'))
    if not dt:continue
    try:o=datetime.fromisoformat(dt.replace('Z','+00:00'))
    except ValueError:continue
    if not NOW-timedelta(hours=12)<=o<=HORIZON:continue
    comp=(g.get('competitions') or [{}])[0];teams=comp.get('competitors') or []
    home=next((name(x) for x in teams if x.get('homeAway')=='home'),'')
    away=next((name(x) for x in teams if x.get('homeAway')=='away'),'')
    title=g.get('name') or (f'{away} @ {home}' if away and home else league)
    key=(league,title,dt)
    if key in existing:continue
    state=((g.get('status') or {}).get('type') or {}).get('state','')
    tag='LIVE' if state=='in' else ('FINAL' if state=='post' else 'UPCOMING')
    events.append({'league':league,'title':title,'start':dt,'tag':tag,'icon':icon,'source':'official_api','sourceDetail':'ESPN NCAA scoreboard'});existing.add(key);added+=1
   cursor=end+timedelta(days=1)
  report[league]=f'espn:{added}; raw_events:{raw}; requests:{((HORIZON.date()-start).days//30)+1}; errors:{errors}'
  if added==0:print(f'WARNING ESPN NCAA adapter returned zero events for {league}; raw_events={raw}; errors={errors}')

def main():
 p=json.loads(FEED.read_text(encoding='utf-8'));events=p.get('events') or [];report={};add_events(events,report)
 unique={}
 for e in events:
  k=(e.get('league'),e.get('title'),e.get('start'))
  if k not in unique or str(e.get('source','')).startswith('official'):unique[k]=e
 p['events']=list(unique.values())
 p['eventCounts']={k:sum(1 for e in p['events'] if e.get('league')==k) for k in sorted({e.get('league') for e in p['events'] if e.get('league')})}
 p.setdefault('officialApiAdapterReport',{})['espnNCAA']=report
 FEED.write_text(json.dumps(p,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 print('ESPN NCAA adapter report:',json.dumps(report,sort_keys=True));print(f'ESPN NCAA adapter total events: {len(p["events"])}')

if __name__=='__main__':main()
