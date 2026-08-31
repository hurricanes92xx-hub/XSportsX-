#!/usr/bin/env python3
"""ESPN-backed NCAA schedule adapter with sport-specific routing and season guards."""
from __future__ import annotations
import json, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; FEED=ROOT/'data'/'schedule_feed.json'
HEADERS={'User-Agent':'Mozilla/5.0 XSportsX-Schedule/5.7','Accept':'application/json,text/plain,*/*'}
NOW=datetime.now(timezone.utc); HORIZON=NOW+timedelta(days=370)
# ESPN's public site API uses sport-specific league identifiers. Soccer is the
# important correction here: NCAA men's soccer is usa.ncaa.m.1, not usa.ncaa.1.
# Field hockey is not exposed consistently through ESPN's scoreboard surface, so
# it is handled as a direct NCAA scoreboard fallback instead of generating 13
# misleading ESPN 404s.
SPORTS=[
 ('NCAA FB','football','college-football','🏈','always'),
 ('NCAA BB','basketball','mens-college-basketball','🏀','winter'),('NCAA WBB','basketball','womens-college-basketball','🏀','winter'),
 ('NCAA Baseball','baseball','college-baseball','⚾','spring'),('NCAA Softball','softball','college-softball','🥎','spring'),
 ("NCAA Men's Soccer",'soccer','usa.ncaa.m.1','⚽','fall'),("NCAA Women's Soccer",'soccer','usa.ncaa.w.1','⚽','fall'),
 ("NCAA Men's Volleyball",'volleyball','mens-college-volleyball','🏐','winter'),("NCAA Women's Volleyball",'volleyball','womens-college-volleyball','🏐','fall'),
 ("NCAA Men's Hockey",'hockey','mens-college-hockey','🏒','winter'),("NCAA Women's Hockey",'hockey','womens-college-hockey','🏒','winter'),
]
FIELD_HOCKEY=("NCAA Women's Field Hockey",'fieldhockey','d1','🏑','fall')

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
def append_game(events,existing,league,icon,g):
 dt=iso(g.get('date'))
 if not dt:return False
 o=datetime.fromisoformat(dt.replace('Z','+00:00'))
 if not NOW-timedelta(hours=12)<=o<=HORIZON:return False
 comp=(g.get('competitions') or [{}])[0];teams=comp.get('competitors') or []
 home=next((name(x) for x in teams if x.get('homeAway')=='home'),''); away=next((name(x) for x in teams if x.get('homeAway')=='away'),'')
 title=g.get('name') or (f'{away} @ {home}' if away and home else league); key=(league,title,dt)
 if key in existing:return False
 state=((g.get('status') or {}).get('type') or {}).get('state','');tag='LIVE' if state=='in' else ('FINAL' if state=='post' else 'UPCOMING')
 events.append({'league':league,'title':title,'start':dt,'tag':tag,'icon':icon,'source':'official_api','sourceDetail':'ESPN NCAA scoreboard'});existing.add(key);return True

def add_field_hockey(events,report,existing):
 league,sport,division,icon,season=FIELD_HOCKEY;added=raw=errors=0; cursor=NOW.date()
 # NCAA's public scoreboard accepts YYYY/MM/DD for non-football sports.
 # Only query the fall window; this avoids treating ESPN's lack of field-hockey
 # coverage as a provider failure.
 while cursor<=HORIZON.date():
  end=min(cursor+timedelta(days=29),HORIZON.date())
  url=f'https://ncaa-api.henrygd.me/scoreboard/fieldhockey/{division}/{cursor:%Y/%m/%d}/all-conf'
  try:root=get_json(url)
  except Exception:errors+=1;cursor=end+timedelta(days=1);continue
  contests=((root.get('data') or {}).get('contests') if isinstance(root,dict) else None) or root.get('games',[]) if isinstance(root,dict) else []
  for g in contests or []:
   raw+=1
   if not isinstance(g,dict):continue
   if append_game(events,existing,league,icon,{'date':g.get('startTimeEpoch') or g.get('startDateTime') or g.get('startTime'),'name':g.get('title') or g.get('name'),'competitions':[{'competitors':[{'homeAway':'home','team':{'displayName':(g.get('homeTeam') or {}).get('name') if isinstance(g.get('homeTeam'),dict) else g.get('homeTeam')}},{'homeAway':'away','team':{'displayName':(g.get('awayTeam') or {}).get('name') if isinstance(g.get('awayTeam'),dict) else g.get('awayTeam')}}]}]}):added+=1
  cursor=end+timedelta(days=1)
 report[league]=f'fieldhockey: {added}; raw_events:{raw}; requests:13; errors:{errors}; season:{season}'
 if added==0:print(f'WARNING field hockey returned zero in-horizon events; raw_events={raw}; errors={errors}')

def add_events(events,report):
 existing={(e.get('league'),e.get('title'),e.get('start')) for e in events}; start=NOW.date()
 for league,sport,slug,icon,season in SPORTS:
  added=raw=errors=0; cursor=start
  while cursor<=HORIZON.date():
   end=min(cursor+timedelta(days=29),HORIZON.date()); url=f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/scoreboard?dates={cursor:%Y%m%d}-{end:%Y%m%d}&limit=1000'
   try:root=get_json(url)
   except Exception: errors+=1; cursor=end+timedelta(days=1); continue
   for g in root.get('events') or []:
    raw+=1
    if not in_season(season,datetime.fromisoformat(iso(g.get('date')).replace('Z','+00:00'))) if g.get('date') and iso(g.get('date')) else False:continue
    if append_game(events,existing,league,icon,g):added+=1
   cursor=end+timedelta(days=1)
  report[league]=f'espn:{added}; raw_events:{raw}; requests:{((HORIZON.date()-start).days//30)+1}; errors:{errors}; season:{season}'
  if added==0 and season not in ('spring','winter') and raw==0:print(f'WARNING ESPN NCAA adapter zero for in-season {league}; raw_events={raw}; errors={errors}')
 add_field_hockey(events,report,existing)
def main():
 p=json.loads(FEED.read_text(encoding='utf-8'));events=p.get('events') or [];report={};add_events(events,report);unique={}
 for e in events:
  k=(e.get('league'),e.get('title'),e.get('start'))
  if k not in unique or str(e.get('source','')).startswith('official'):unique[k]=e
 p['events']=list(unique.values());p['eventCounts']={k:sum(1 for e in p['events'] if e.get('league')==k) for k in sorted({e.get('league') for e in p['events'] if e.get('league')})};p.setdefault('officialApiAdapterReport',{})['espnNCAA']=report;FEED.write_text(json.dumps(p,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print('ESPN NCAA adapter report:',json.dumps(report,sort_keys=True));print(f'ESPN NCAA adapter total events: {len(p["events"])}')
if __name__=='__main__':main()
