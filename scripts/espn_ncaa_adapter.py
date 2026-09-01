#!/usr/bin/env python3
"""ESPN-backed NCAA schedule adapter with scoreboard logo hydration."""
from __future__ import annotations
import json,re,urllib.request
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; FEED=ROOT/'data'/'schedule_feed.json'; CACHE=ROOT/'data'/'team_logo_map.json'
HEADERS={'User-Agent':'Mozilla/5.0 XSportsX-Schedule/6.0','Accept':'application/json,text/plain,*/*'}
NOW=datetime.now(timezone.utc); HORIZON=NOW+timedelta(days=370)
SPORTS=[
 ('NCAA FB','football','college-football','🏈','always',None),('NCAA FCS','football','college-football','🏈','always','81'),
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
def norm(s):return re.sub(r'\s+',' ',re.sub(r'[^A-Z0-9]+',' ',str(s or '').upper())).strip()
def team_obj(c):return (c or {}).get('team') or (c or {}) if isinstance(c,dict) else {}
def name(c):
 t=team_obj(c)
 for k in ('displayName','shortDisplayName','name','abbreviation'):
  if isinstance(t.get(k),str) and t[k].strip():return t[k].strip()
 return ''
def logo(c):
 for x in team_obj(c).get('logos') or []:
  if isinstance(x,dict) and x.get('href'):return str(x['href']).strip()
 return ''
def tid(c):return str(team_obj(c).get('id') or '').strip()
def deterministic_logo(sport,team_id):
 if not team_id:return ''
 # ESPN's stable team-logo CDN paths for college team identities.
 return f'https://a.espncdn.com/i/teamlogos/{sport}/500/{team_id}.png'
def resolved_logo(c,sport):return logo(c) or deterministic_logo(sport,tid(c))
def in_season(kind,dt):return {'always':True,'fall':dt.month in (8,9,10,11),'winter':dt.month in (11,12,1,2,3,4,5),'spring':dt.month in (2,3,4,5,6)}[kind]
def cache_team(cache,league,c,sport):
 l=resolved_logo(c,sport)
 if not l:return 0
 t=team_obj(c); names={t.get('displayName'),t.get('shortDisplayName'),t.get('name'),t.get('abbreviation'),t.get('slug'),t.get('id')}; changed=0
 for n in names:
  if n:
   k=f'{league}|{norm(n)}'
   if cache.get(k)!=l:cache[k]=l;changed+=1
 return changed
def add_events(events,report,cache):
 existing={(e.get('league'),e.get('title'),e.get('start')):e for e in events}; start=NOW.date();cache_changed=updated=0;id_fallbacks=0
 for league,sport,slug,icon,season,group in SPORTS:
  added=raw=errors=0; cursor=start
  while cursor<=HORIZON.date():
   end=min(cursor+timedelta(days=29),HORIZON.date()); extra=f'&groups={group}' if group else ''
   url=f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/scoreboard?dates={cursor:%Y%m%d}-{end:%Y%m%d}&limit=1000{extra}'
   try:root=get_json(url)
   except Exception:errors+=1;cursor=end+timedelta(days=1);continue
   for g in root.get('events') or []:
    raw+=1;dt=iso(g.get('date'))
    if not dt:continue
    o=datetime.fromisoformat(dt.replace('Z','+00:00'))
    if not NOW-timedelta(hours=12)<=o<=HORIZON or not in_season(season,o):continue
    comp=(g.get('competitions') or [{}])[0];teams=comp.get('competitors') or []
    hc=next((x for x in teams if x.get('homeAway')=='home'),{});ac=next((x for x in teams if x.get('homeAway')=='away'),{})
    home=name(hc);away=name(ac);hl=resolved_logo(hc,sport);al=resolved_logo(ac,sport)
    if tid(hc) and not logo(hc):id_fallbacks+=1
    if tid(ac) and not logo(ac):id_fallbacks+=1
    cache_changed+=cache_team(cache,league,hc,sport)+cache_team(cache,league,ac,sport)
    title=g.get('name') or (f'{away} @ {home}' if away and home else league);key=(league,title,dt);old=existing.get(key)
    if old is not None:
     changed=False
     if al and not old.get('awayLogo'):old['awayLogo']=al;changed=True
     if hl and not old.get('homeLogo'):old['homeLogo']=hl;changed=True
     if tid(ac) and not old.get('awayTeamId'):old['awayTeamId']=tid(ac);changed=True
     if tid(hc) and not old.get('homeTeamId'):old['homeTeamId']=tid(hc);changed=True
     if changed:updated+=1
     continue
    state=((g.get('status') or {}).get('type') or {}).get('state','');tag='LIVE' if state=='in' else ('FINAL' if state=='post' else 'UPCOMING')
    e={'league':league,'title':title,'start':dt,'tag':tag,'icon':icon,'source':'official_api','sourceDetail':f'ESPN NCAA scoreboard'+(' FCS group' if group else '')}
    if away:e['away']=away
    if home:e['home']=home
    if al:e['awayLogo']=al
    if hl:e['homeLogo']=hl
    if tid(ac):e['awayTeamId']=tid(ac)
    if tid(hc):e['homeTeamId']=tid(hc)
    events.append(e);existing[key]=e;added+=1
   cursor=end+timedelta(days=1)
  status='added' if added else ('duplicate_only' if raw and errors==0 else 'empty');report[league]=f'espn:{added}; raw_events:{raw}; requests:{((HORIZON.date()-start).days//30)+1}; errors:{errors}; season:{season}; status:{status}'
  if added==0 and season not in ('spring','winter') and not(raw and errors==0):print(f'WARNING ESPN NCAA adapter zero for in-season {league}; raw_events={raw}; errors={errors}')
 report['_logo_hydration']=f'cache_entries_changed:{cache_changed}; existing_events_updated:{updated}; deterministic_id_fallbacks:{id_fallbacks}'
def main():
 p=json.loads(FEED.read_text(encoding='utf-8'));events=p.get('events') or [];c=json.loads(CACHE.read_text(encoding='utf-8')) if CACHE.exists() else {'version':4,'teams':{},'sources':{}};cache=c.setdefault('teams',{});report={};add_events(events,report,cache)
 unique={}
 for e in events:
  k=(e.get('league'),e.get('title'),e.get('start'))
  if k not in unique or str(e.get('source','')).startswith('official'):unique[k]=e
 p['events']=list(unique.values());p['eventCounts']={k:sum(1 for e in p['events'] if e.get('league')==k) for k in sorted({e.get('league') for e in p['events'] if e.get('league')})};p.setdefault('officialApiAdapterReport',{})['espnNCAA']=report;c['generatedAt']=datetime.now(timezone.utc).isoformat();CACHE.write_text(json.dumps(c,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8');FEED.write_text(json.dumps(p,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print('ESPN NCAA adapter report:',json.dumps(report,sort_keys=True));print(f'ESPN NCAA adapter total events: {len(p["events"])}')
if __name__=='__main__':main()
