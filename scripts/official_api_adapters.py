#!/usr/bin/env python3
"""Authoritative schedule adapters for unreliable providers."""
from __future__ import annotations
import json
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FEED=ROOT/'data'/'schedule_feed.json'
HEADERS={'User-Agent':'XSportsX-Schedule/5.3','Accept':'application/json,text/plain,*/*','Accept-Language':'en-US,en;q=0.9'}
NOW=datetime.now(timezone.utc); HORIZON=NOW+timedelta(days=370)
NCAA=[
 ('NCAA BB','basketball-men','d1','🏀'),('NCAA WBB','basketball-women','d1','🏀'),('NCAA Baseball','baseball','d1','⚾'),('NCAA Softball','softball','d1','🥎'),
 ("NCAA Men's Hockey",'icehockey-men','d1','🏒'),("NCAA Women's Hockey",'icehockey-women','d1','🏒'),("NCAA Men's Soccer",'soccer-men','d1','⚽'),("NCAA Women's Soccer",'soccer-women','d1','⚽'),
 ("NCAA Men's Lacrosse",'lacrosse-men','d1','🥍'),("NCAA Women's Lacrosse",'lacrosse-women','d1','🥍'),("NCAA Men's Volleyball",'volleyball-men','d1','🏐'),("NCAA Women's Volleyball",'volleyball-women','d1','🏐'),
 ("NCAA Men's Water Polo",'waterpolo-men','d1','🤽'),("NCAA Women's Water Polo",'waterpolo-women','d1','🤽'),("NCAA Women's Field Hockey",'fieldhockey-women','d1','🏑'),('NCAA Beach Volleyball','beach-volleyball','d1','🏐')]
NASCAR=[('NASCAR Cup',1,'🏁'),('NASCAR Xfinity',2,'🏁'),('NASCAR Truck',3,'🏁')]

def get_json(url):
 req=urllib.request.Request(url,headers=HEADERS)
 with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read().decode('utf-8','ignore'))

def iso(v):
 if v is None:return None
 if isinstance(v,(int,float)):
  try:return datetime.fromtimestamp(float(v)/1000 if float(v)>10_000_000_000 else float(v),tz=timezone.utc).isoformat().replace('+00:00','Z')
  except Exception:return None
 s=str(v).strip()
 for x in (s,s.replace('Z','+00:00'),s.replace('z','+00:00')):
  try:return datetime.fromisoformat(x).astimezone(timezone.utc).isoformat().replace('+00:00','Z')
  except ValueError:pass
 return None

def team(v):
 if isinstance(v,str):return v.strip()
 if isinstance(v,dict):
  for k in ('nameShort','shortName','short','displayName','fullName','name','title','teamName'):
   if isinstance(v.get(k),str) and v[k].strip():return v[k].strip()
  names=v.get('names')
  if isinstance(names,dict):
   for k in ('short','medium','full','char6'):
    if isinstance(names.get(k),str) and names[k].strip():return names[k].strip()
 return ''

def ncaa_games(root):
 """Normalize modern NCAA GraphQL contests and legacy games."""
 contests=((root.get('data') or {}).get('contests') if isinstance(root,dict) else None)
 if isinstance(contests,list):
  out=[]
  for g in contests:
   if not isinstance(g,dict):continue
   teams=g.get('teams') or []
   home=next((t for t in teams if isinstance(t,dict) and t.get('isHome') is True),None)
   away=next((t for t in teams if isinstance(t,dict) and t.get('isHome') is False),None)
   dt=iso(g.get('startTimeEpoch')) or iso(g.get('startDateTimeUtc'))
   if not dt and g.get('startDate') and g.get('startTime'):
    try:dt=datetime.fromisoformat(f"{g['startDate']}T{g['startTime']}").replace(tzinfo=timezone.utc).isoformat().replace('+00:00','Z')
    except ValueError:dt=None
   if dt and (home or away):out.append((team(away),team(home),dt,str(g.get('title') or '').strip()))
  return out
 games=root.get('games') if isinstance(root,dict) else None
 out=[]
 for g in games if isinstance(games,list) else []:
  if not isinstance(g,dict):continue
  away=team(g.get('away') or g.get('awayTeam') or g.get('visitor'));home=team(g.get('home') or g.get('homeTeam') or g.get('host'))
  dt=iso(g.get('startTimeEpoch') or g.get('startDateTimeUtc') or g.get('startDateTime'))
  if not dt and g.get('startDate') and g.get('startTime'):
   try:dt=datetime.strptime(f"{g['startDate']} {g['startTime']}",'%Y-%m-%d %I:%M%p ET').replace(tzinfo=timezone.utc).isoformat().replace('+00:00','Z')
   except ValueError:dt=None
  if dt and (away or home or g.get('title')):out.append((away,home,dt,str(g.get('title') or '').strip()))
 return out

def add_ncaa(events,report):
 """Use NCAA's current season schedule GraphQL route, not the now-unreliable daily scoreboard wrapper."""
 existing={(e.get('league'),e.get('title'),e.get('start')) for e in events}
 season=NOW.year
 for league,sport,division,icon in NCAA:
  added=0;errors=[]
  # schedule-alt is the maintained API's modern season-wide route. One request per sport.
  url=f'https://ncaa-api.henrygd.me/schedule-alt/{sport}/{division}/{season}'
  try:root=get_json(url)
  except Exception as exc:
   report.setdefault('ncaa',{})[league]=f'official_api:0; requests:1; errors:1; error:{exc}'
   print(f'WARNING NCAA adapter request failed for {league}: {exc}');continue
  games=ncaa_games(root)
  for away,home,dt,raw in games:
   try:o=datetime.fromisoformat(dt.replace('Z','+00:00'))
   except ValueError:continue
   if not NOW-timedelta(hours=12)<=o<=HORIZON:continue
   title=f'{away} @ {home}' if away and home else (raw or home or away or league)
   key=(league,title,dt)
   if key in existing:continue
   tag='LIVE' if o<=NOW+timedelta(minutes=5) else ('FINAL' if o<=NOW else 'UPCOMING')
   events.append({'league':league,'title':title,'start':dt,'tag':tag,'icon':icon,'source':'official_api','sourceDetail':'NCAA season schedule API'});existing.add(key);added+=1
  report.setdefault('ncaa',{})[league]=f'official_api:{added}; requests:1; errors:0; raw_events:{len(games)}'
  if added==0:print(f'WARNING NCAA adapter returned zero in-horizon events for {league}; raw_events={len(games)}')

def nascar_races(root,series_id):
 rows=[]
 def walk(v,ctx=None):
  if isinstance(v,dict):
   c=dict(ctx or {});c.update({k:v[k] for k in ('series_id','seriesId','race_id','race_name','track_name','event_name','date_scheduled','race_date','start_time_utc','startTimeUtc') if k in v})
   if isinstance(v.get('schedule'),list):
    for s in v['schedule']:
     if isinstance(s,dict):rows.append({**c,**s})
   elif v.get('start_time_utc') or v.get('startTimeUtc'):rows.append(c)
   for x in v.values():walk(x,c)
  elif isinstance(v,list):
   for x in v:walk(x,ctx)
 walk(root);return [r for r in rows if int(r.get('series_id') or r.get('seriesId') or 0)==series_id]

def add_nascar(events,report):
 year=NOW.year;urls={1:f'https://cf.nascar.com/cacher/{year}/1/race_list_basic.json',2:f'https://cf.nascar.com/cacher/{year}/race_list_basic.json',3:f'https://cf.nascar.com/cacher/{year}/race_list_basic.json'};loaded={}
 for sid in (1,2,3):
  try:loaded[sid]=get_json(urls[sid])
  except Exception as exc:report.setdefault('nascar',{})[next(n for n,s,_ in NASCAR if s==sid)]=f'failed: {exc}'
 existing={(e.get('league'),e.get('title'),e.get('start')) for e in events}
 for league,sid,icon in NASCAR:
  added=0
  for r in nascar_races(loaded.get(sid),sid) if loaded.get(sid) else []:
   dt=iso(r.get('start_time_utc') or r.get('startTimeUtc') or r.get('date_scheduled') or r.get('race_date'))
   if not dt:continue
   try:o=datetime.fromisoformat(dt.replace('Z','+00:00'))
   except ValueError:continue
   if not NOW-timedelta(hours=12)<=o<=HORIZON:continue
   title=' — '.join(x for x in (str(r.get('race_name') or r.get('event_name') or league),str(r.get('track_name') or '')) if x);key=(league,title,dt)
   if key in existing:continue
   events.append({'league':league,'title':title,'start':dt,'tag':'LIVE' if o<=NOW else 'UPCOMING','icon':icon,'source':'official_api','sourceDetail':'NASCAR CF schedule cache'});existing.add(key);added+=1
  report.setdefault('nascar',{})[league]=f'official_api:{added}'

def add_mlb(events,report):
 try:root=get_json(f'https://statsapi.mlb.com/api/v1/schedule?sportId=1&season={NOW.year}&startDate={NOW.date()}&endDate={HORIZON.date()}&hydrate=team,venue,broadcasts')
 except Exception as exc:report['MLB']=f'failed: {exc}';return
 existing={(e.get('league'),e.get('title'),e.get('start')) for e in events};added=0
 for day in root.get('dates',[]):
  for g in day.get('games',[]):
   dt=iso(g.get('gameDate'));t=g.get('teams') or {};away=team((t.get('away') or {}).get('team'));home=team((t.get('home') or {}).get('team'))
   if not dt:continue
   title=f'{away} @ {home}' if away and home else 'MLB';key=('MLB',title,dt)
   if key in existing:continue
   state=((g.get('status') or {}).get('abstractGameState') or '').lower();tag='LIVE' if state=='live' else ('FINAL' if state=='final' else 'UPCOMING')
   events.append({'league':'MLB','title':title,'start':dt,'tag':tag,'icon':'⚾','source':'official_api','sourceDetail':'MLB Stats API'});existing.add(key);added+=1
 report['MLB']=f'official_api:{added}'

def main():
 payload=json.loads(FEED.read_text(encoding='utf-8'));events=payload.get('events') or [];report={};add_ncaa(events,report);add_nascar(events,report);add_mlb(events,report)
 unique={}
 for e in events:
  k=(e.get('league'),e.get('title'),e.get('start'))
  if k not in unique or str(e.get('source','')).startswith('official'):unique[k]=e
 payload['events']=list(unique.values());counts={}
 for e in payload['events']:counts[e.get('league','')]=counts.get(e.get('league',''),0)+1
 payload['eventCounts']=counts;payload['officialApiAdapterReport']=report;FEED.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print('official API adapter report:',json.dumps(report,sort_keys=True));print(f'official API adapter total events: {len(payload["events"])}')
if __name__=='__main__':main()
