#!/usr/bin/env python3
"""ESPN-backed NCAA schedule adapter with sport-specific routing, FCS coverage, and season guards."""
from __future__ import annotations
import json, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; FEED=ROOT/'data'/'schedule_feed.json'
HEADERS={'User-Agent':'Mozilla/5.0 XSportsX-Schedule/5.9','Accept':'application/json,text/plain,*/*'}
NOW=datetime.now(timezone.utc); HORIZON=NOW+timedelta(days=370)
SPORTS=[
 ('NCAA FB','football','college-football','🏈','always',None),
 ('NCAA FCS','football','college-football','🏈','always','81'),
 ('NCAA BB','basketball','mens-college-basketball','🏀','winter',None),('NCAA WBB','basketball','womens-college-basketball','🏀','winter',None),
 ('NCAA Baseball','baseball','college-baseball','⚾','spring',None),('NCAA Softball','softball','college-softball','🥎','spring',None),
 ("NCAA Men's Soccer",'soccer','usa.ncaa.m.1','⚽','fall',None),("NCAA Women's Soccer",'soccer','usa.ncaa.w.1','⚽','fall',None),
 ("NCAA Men's Volleyball",'volleyball','mens-college-volleyball','🏐','winter',None),("NCAA Women's Volleyball",'volleyball','womens-college-volleyball','🏐','fall',None),
 ("NCAA Men's Hockey",'hockey','mens-college-hockey','🏒','winter',None),("NCAA Women's Hockey",'hockey','womens-college-hockey','🏒','winter',None),
 ("NCAA Women's Field Hockey",'field-hockey','womens-college-field-hockey','🏑','fall',None)]

def get_json(url):
 req=urllib.request.Request(url,headers=HEADERS)
 with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read().decode('utf-8','ignore'))
def iso(v):
 try:return datetime.fromisoformat(str(v).replace('Z','+00:00')).astimezone(timezone.utc).isoformat().replace('+00:00','Z') if v else None
 except ValueError:return None
def name(team):
 t=(team or {}).get('team') or (team or {}) if isinstance(team,dict) else {}
 for k in ('displayName','shortDisplayName','name','abbreviation'):
  if isinstance(t.get(k),str) and t[k].strip():return t[k].strip()
 return ''
def in_season(kind,dt):
 m=dt.month
 return {'always':True,'fall':m in (8,9,10,11),'winter':m in (11,12,1,2,3,4,5),'spring':m in (2,3,4,5,6)}[kind]
def add_events(events,report):
 existing={(e.get('league'),e.get('title'),e.get('start')) for e in events}; start=NOW.date()
 for league,sport,slug,icon,season,group in SPORTS:
  added=raw=errors=0; cursor=start
  while cursor<=HORIZON.date():
   end=min(cursor+timedelta(days=29),HORIZON.date()); extra=f'&groups={group}' if group else ''
   url=f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/scoreboard?dates={cursor:%Y%m%d}-{end:%Y%m%d}&limit=1000{extra}'
   try:root=get_json(url)
   except Exception: errors+=1; cursor=end+timedelta(days=1); continue
   for g in root.get('events') or []:
    raw+=1;dt=iso(g.get('date'))
    if not dt:continue
    o=datetime.fromisoformat(dt.replace('Z','+00:00'))
    if not NOW-timedelta(hours=12)<=o<=HORIZON or not in_season(season,o):continue
    comp=(g.get('competitions') or [{}])[0];teams=comp.get('competitors') or []
    home=next((name(x) for x in teams if x.get('homeAway')=='home'),''); away=next((name(x) for x in teams if x.get('homeAway')=='away'),'')
    title=g.get('name') or (f'{away} @ {home}' if away and home else league); key=(league,title,dt)
    if key in existing:continue
    state=((g.get('status') or {}).get('type') or {}).get('state','');tag='LIVE' if state=='in' else ('FINAL' if state=='post' else 'UPCOMING')
    events.append({'league':league,'title':title,'start':dt,'tag':tag,'icon':icon,'source':'official_api','sourceDetail':f'ESPN NCAA scoreboard'+(' FCS group' if group else '')});existing.add(key);added+=1
   cursor=end+timedelta(days=1)
  status='added' if added else ('duplicate_only' if raw and errors==0 else 'empty')
  report[league]=f'espn:{added}; raw_events:{raw}; requests:{((HORIZON.date()-start).days//30)+1}; errors:{errors}; season:{season}; status:{status}'
  if added==0 and season not in ('spring','winter') and not (raw and errors==0):print(f'WARNING ESPN NCAA adapter zero for in-season {league}; raw_events={raw}; errors={errors}')
def main():
 p=json.loads(FEED.read_text(encoding='utf-8'));events=p.get('events') or [];report={};add_events(events,report);unique={}
 for e in events:
  k=(e.get('league'),e.get('title'),e.get('start'))
  if k not in unique or str(e.get('source','')).startswith('official'):unique[k]=e
 p['events']=list(unique.values());p['eventCounts']={k:sum(1 for e in p['events'] if e.get('league')==k) for k in sorted({e.get('league') for e in p['events'] if e.get('league')})};p.setdefault('officialApiAdapterReport',{})['espnNCAA']=report;FEED.write_text(json.dumps(p,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print('ESPN NCAA adapter report:',json.dumps(report,sort_keys=True));print(f'ESPN NCAA adapter total events: {len(p["events"])}')
if __name__=='__main__':main()
