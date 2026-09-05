#!/usr/bin/env python3
from __future__ import annotations
import json,os,re,urllib.parse,urllib.request
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];FEED=ROOT/'data/schedule_feed.json';UA='XSportsX-SupplementalAdapters/1.4'
def get(url,headers=None,timeout=10):
 req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json,text/plain,*/*',**(headers or {})})
 with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode('utf-8','ignore'))
def text(url,timeout=10):
 req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml,*/*'})
 with urllib.request.urlopen(req,timeout=timeout) as r:return r.read().decode('utf-8','ignore')
def norm(v):return re.sub(r'[^a-z0-9]+','',str(v or '').lower())
def iso(v):
 if not v:return ''
 try:return datetime.fromisoformat(str(v).replace('Z','+00:00')).astimezone(timezone.utc).isoformat().replace('+00:00','Z')
 except:return ''
def name(v):
 if isinstance(v,str):return v.strip()
 if isinstance(v,dict):return str(v.get('name') or v.get('displayName') or v.get('shortName') or v.get('teamName') or '').strip()
 return str(v or '').strip()
def row(league,title,start,source,eid,live=False,home='',away=''):
 return {'league':league,'title':title,'start':start,'startUtc':start,'tag':'LIVE' if live else 'UPCOMING','status':'LIVE' if live else 'UPCOMING','state':'in' if live else 'pre','home':home,'away':away,'source':source,'providerEventId':eid,'liveEvidenceSource':source if live else ''}
def _espn_events(sport,league,days):
 out=[]
 for day in days:
  ds=day.strftime('%Y%m%d');x=None
  for base in ('https://site.api.espn.com/apis/site/v2','https://site.web.api.espn.com/apis/site/v2'):
   try:x=get(f'{base}/sports/{sport}/{league}/scoreboard?dates={ds}&limit=1000');break
   except Exception:pass
  if not x:continue
  for ev in x.get('events') or []:
   comp=(ev.get('competitions') or [{}])[0];typ=((comp.get('status') or {}).get('type') or {});state=str(typ.get('state') or '').lower();start=iso(ev.get('date'));nm=str(ev.get('name') or ev.get('shortName') or league)
   if start:out.append(row(league,nm,start,f'espn-{league}',f'espn:{ev.get("id")}',state=='in'))
 return out
def f1():
 now=datetime.now(timezone.utc);days=[now.date()+timedelta(days=d) for d in (-1,0,1)];out=[];diag={'status':'ok','espn':False,'espnEvents':0,'live':0,'upcoming':0,'openf1Sessions':0,'errors':[]}
 for r in _espn_events('racing','f1',days):diag['espn']=True;diag['espnEvents']+=1;out.append(r);diag['live']+=int(r['tag']=='LIVE');diag['upcoming']+=int(r['tag']=='UPCOMING')
 if out:return out,diag
 try:meetings=get(f'https://api.openf1.org/v1/meetings?year={now.year}')
 except Exception as e:return out,{**diag,'status':'unavailable','errors':[type(e).__name__]}
 for m in meetings if isinstance(meetings,list) else []:
  try:sessions=get(f"https://api.openf1.org/v1/sessions?meeting_key={m.get('meeting_key')}")
  except Exception as e:diag['errors'].append(type(e).__name__);continue
  for s in sessions if isinstance(sessions,list) else []:
   st=iso(s.get('date_start'));en=iso(s.get('date_end'))
   if not st:continue
   a=datetime.fromisoformat(st.replace('Z','+00:00'));b=datetime.fromisoformat(en.replace('Z','+00:00')) if en else a+timedelta(hours=2);diag['openf1Sessions']+=1;title=f"{m.get('meeting_name') or m.get('country_name') or 'Formula 1'} — {s.get('session_name') or 'Session'}"
   if a<=now<=b+timedelta(minutes=2):out.append(row('F1',title,st,'openf1-schedule',f"openf1:{s.get('session_key')}",True));diag['live']+=1
   elif a<=now+timedelta(days=8) and b>=now:out.append(row('F1',title,st,'openf1-schedule',f"openf1:{s.get('session_key')}",False));diag['upcoming']+=1
 if not out:diag['status']='no-data'
 return out,diag
def _core_event_detail(ev):
 ref=ev.get('$ref') or ev.get('ref') or ''
 if ref:
  try:return get(ref)
  except Exception:pass
 return ev if isinstance(ev,dict) else {}
def _core_state(d):
 comp=(d.get('competitions') or [{}])[0] if isinstance(d,dict) else {};status=comp.get('status') or d.get('status') or {};typ=status.get('type') or status if isinstance(status,dict) else {};state=str(typ.get('state') or status.get('state') or '').lower();namev=str(typ.get('name') or status.get('name') or status.get('detail') or '').lower();live=state=='in' or bool(re.search(r'live|in progress|green flag|underway',namev));return live,state,comp
def nascar():
 now=datetime.now(timezone.utc);cutoff=now+timedelta(days=14);out=[];diag={'status':'ok','official':False,'espn':False,'core':False,'espnEvents':0,'coreEvents':0,'live':0,'schedule':0,'errors':[]}
 # Official feed remains first choice. A blocked official endpoint is recorded once;
 # the independent ESPN sources then provide the schedule/live fallback.
 for v in ('1','2'):
  try:
   x=get(f'https://feed.nascar.com/api/LiveFeed?v={v}',{'Referer':'https://www.nascar.com/','Origin':'https://www.nascar.com/'});diag['official']=True
   for z in x if isinstance(x,list) else [x]:
    if not isinstance(z,dict) or str(z.get('series_id') or z.get('seriesId'))!='3':continue
    rid=z.get('race_id') or z.get('raceId') or z.get('run_id');nm=z.get('run_name') or z.get('event_name') or 'NASCAR Craftsman Truck Series';st=iso(z.get('time_of_day_os') or z.get('start_time_utc') or z.get('start_time'));out.append(row('NASCAR Truck',nm,st,'nascar-livefeed-official',f'nascar:live:{rid}',True));diag['live']+=1
   if out:return out,diag
  except Exception as e:diag['errors'].append(f'official:{type(e).__name__}')
 days=[now.date()+timedelta(days=d) for d in range(-2,15)]
 for r in _espn_events('racing','nascar-truck',days):diag['espn']=True;diag['espnEvents']+=1;out.append(r);diag['live']+=int(r['tag']=='LIVE');diag['schedule']+=1
 try:
  x=get('https://sports.core.api.espn.com/v2/sports/racing/leagues/nascar-truck/events?limit=1000');diag['core']=True
  items=x.get('items') or x.get('events') or []
  for ev in items:
   d=_core_event_detail(ev)
   st=iso(d.get('date') or d.get('startDate') or d.get('startTime'))
   if not st:continue
   dt=datetime.fromisoformat(st.replace('Z','+00:00'))
   if dt<now-timedelta(days=2) or dt>cutoff:continue
   live,state,comp=_core_state(d);nm=str(d.get('name') or d.get('shortName') or comp.get('name') or 'NASCAR Craftsman Truck Series');eid=d.get('id') or ev.get('id') or norm(nm)+st
   out.append(row('NASCAR Truck',nm,st,'espn-core-nascar-truck',f'espn-core:{eid}',live));diag['coreEvents']+=1;diag['schedule']+=1;diag['live']+=int(live)
 except Exception as e:diag['errors'].append(f'core:{type(e).__name__}')
 # Dedupe by provider id/title/start and keep LIVE over UPCOMING.
 ded={}
 for r in out:
  key=(norm(r.get('title')),r.get('startUtc'));old=ded.get(key)
  if old is None or (r['tag']=='LIVE' and old['tag']!='LIVE'):ded[key]=r
 out=list(ded.values())
 if not out:diag['status']='unavailable' if not diag['official'] and not diag['espn'] and not diag['core'] else 'no-data'
 return out,diag
def _cricket_live_status(status):
 if isinstance(status,dict):
  parts=[str(status.get(k) or '') for k in ('type','state','name','shortDetail','detail','description')];typ=status.get('type')
  if isinstance(typ,dict):parts += [str(typ.get(k) or '') for k in ('state','name','shortDetail','detail')]
  s=' '.join(parts);return bool(re.search(r'live|in progress|inprogress|stumps|innings|play',s,re.I)) and not bool(re.search(r'final|postponed|cancelled|scheduled',s,re.I))
 return bool(re.search(r'live|in progress|stumps|innings|play',str(status),re.I))
def cricket():
 out=[];diag={'status':'ok','espnPersonalized':False,'espnSummary':0,'espnCore':0,'cricketdata':False,'criclive':False,'series':0,'matches':0,'live':0,'errors':[]}
 try:
  x=get('https://site.api.espn.com/apis/personalized/v2/scoreboard/header?sport=cricket&region=in&tz=Asia/Calcutta');diag['espnPersonalized']=True
  for sport in x.get('sports') or []:
   for league in sport.get('leagues') or []:
    lname=str(league.get('name') or league.get('shortName') or '')
    if not re.search(r'IPL|ICC|T20|Twenty20',lname,re.I):continue
    diag['series']+=1;lid=str(league.get('id') or '')
    for ev in league.get('events') or []:
     eid=str(ev.get('id') or '');start=iso(ev.get('date') or ev.get('startDate'));title=str(ev.get('name') or ev.get('shortName') or lname);live=_cricket_live_status(ev.get('status'))
     if lid and eid:
      try:
       sm=get(f'https://site.web.api.espn.com/apis/site/v2/sports/cricket/{lid}/summary?contentorigin=espn&event={eid}&lang=en&region=in');diag['espnSummary']+=1;hs=((sm.get('header') or {}).get('competitions') or [{}])[0];live=live or _cricket_live_status(hs.get('status') or sm.get('gameInfo'));start=iso(hs.get('date') or start);title=str(hs.get('name') or title)
      except Exception as e:diag['errors'].append(f'summary:{type(e).__name__}')
     if start or eid:out.append(row('IPL' if re.search(r'IPL',lname,re.I) else 'ICC T20',title,start,'espn-cricket-personalized',f'espn-cricket:{lid}:{eid}',live));diag['matches']+=1;diag['live']+=int(live)
 except Exception as e:diag['errors'].append(f'espn:{type(e).__name__}')
 # Keep existing optional keyed providers untouched.
 key=os.getenv('CRICKETDATA_API_KEY','').strip()
 if key:
  try:
   x=get(f'https://api.cricapi.com/v1/currentMatches?apikey={urllib.parse.quote(key)}&offset=0');diag['cricketdata']=True
   for z in x.get('data') or []:
    nn=norm(z.get('name') or z.get('matchType'));league='IPL' if 'ipl' in nn else 'ICC T20' if 't20' in nn or 'icc' in nn else '';ti=z.get('teamInfo') or [];home=name(ti[0] if ti else z.get('homeTeam'));away=name(ti[1] if len(ti)>1 else z.get('awayTeam'));live=str(z.get('matchStarted')).lower()=='true' and str(z.get('matchEnded')).lower()!='true'
    if league and home and away:out.append(row(league,f'{away} @ {home}',iso(z.get('dateTimeGMT') or z.get('dateTime')),'cricketdata',f"cricketdata:{z.get('id') or nn}",live,home,away));diag['live']+=int(live)
  except Exception as e:diag['errors'].append(f'cricketdata:{type(e).__name__}')
 key=os.getenv('CRICLIVE_API_KEY','').strip()
 if key:
  try:
   x=get('https://cricketliveapi.com/api/v1/live',{'X-API-Key':key});diag['criclive']=True
   for z in x.get('data') or []:
    comp=str(z.get('series_name') or z.get('series') or '');nn=norm(comp);league='IPL' if 'ipl' in nn else 'ICC T20' if 't20' in nn or 'icc' in nn else '';a=z.get('first_team') or {};b=z.get('second_team') or {};home=name(a.get('full_name') or a.get('name'));away=name(b.get('full_name') or b.get('name'))
    if league and home and away:out.append(row(league,f'{away} @ {home}','','criclive',f"criclive:{z.get('match_id')}",True,home,away));diag['live']+=1
  except Exception as e:diag['errors'].append(f'criclive:{type(e).__name__}')
 if not out:diag['status']='no-data'
 return out,diag
def _walk_json(v,found):
 if isinstance(v,dict):
  if ('startDate' in v or 'start' in v or 'date' in v) and ('name' in v or 'title' in v):found.append(v)
  for x in v.values():_walk_json(x,found)
 elif isinstance(v,list):
  for x in v:_walk_json(x,found)
def _xgames_event_pages():
 # The public /schedule page is a marketing index and no longer exposes the
 # structured event payload to server-side clients. Official event pages do.
 return [
  ('https://www.xgames.com/events/sacramento-2026/','Sacramento 2026'),
  ('https://www.xgames.com/events/japan-2026/','Chiba 2026'),
  ('https://www.xgames.com/events/new-orleans-2026/','NOLA 2026'),
  ('https://www.xgames.com/events/aspen-2026/','Aspen 2026'),
  ('https://www.xgames.com/events/xgl-winter-draft-2026/','XGL Winter Draft 2026'),
 ]
def xgames():
 out=[];diag={'status':'official-event-pages','live':0,'source':'xgames-official-event-pages','events':0,'pages':0,'errors':[]}
 for url,label in _xgames_event_pages():
  try:
   html=text(url);diag['pages']+=1;found=[]
   for raw in re.findall(r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',html,re.I|re.S):
    try:_walk_json(json.loads(raw),found)
    except Exception:pass
   for raw in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',html,re.I|re.S):
    try:_walk_json(json.loads(raw),found)
    except Exception:pass
   # Event pages also expose visible schedule times. Capture only explicit X Games
   # competition labels, never invent a LIVE state from page presence alone.
   for obj in found:
    st=iso(obj.get('startDate') or obj.get('start') or obj.get('date') or obj.get('startTime'));title=str(obj.get('name') or obj.get('title') or '').strip()
    if not st or not title or not re.search(r'X Games|BMX|Skate|Ski|Snowboard|Moto|Scooter|XGL|Draft',title,re.I):continue
    key=(norm(title),st)
    if any((norm(x.get('title'))==key[0] and x.get('startUtc')==st) for x in out):continue
    out.append(row('X Games',title,st,'xgames-official-event-page',f'xgames:{key[0]}:{st}',False));diag['events']+=1
  except Exception as e:diag['errors'].append(f'{label}:{type(e).__name__}')
 return out,diag
def main():
 if not FEED.exists():raise SystemExit('missing schedule feed')
 p=json.loads(FEED.read_text());events=[e for e in p.get('events') or [] if isinstance(e,dict)];checked=str((p.get('liveSweep') or {}).get('checkedAtUtc') or datetime.now(timezone.utc).isoformat().replace('+00:00','Z'));allrows=[];diagnostics={}
 for n,fn in (('F1',f1),('NASCAR Truck',nascar),('Cricket',cricket),('X Games',xgames)):
  try:r,d=fn();allrows.extend(r);diagnostics[n]=d
  except Exception as e:diagnostics[n]={'status':'error','errors':[type(e).__name__]}
 added=live=0
 for r in allrows:
  match=next((e for e in events if norm(e.get('league'))==norm(r.get('league')) and (norm(e.get('title'))==norm(r.get('title')) or (norm(e.get('home'))==norm(r.get('home')) and norm(e.get('away'))==norm(r.get('away'))))),None)
  if match and r['tag']=='LIVE':match.update({'tag':'LIVE','status':'LIVE','state':'in','liveStateSource':'supplemental-adapter','liveEvidence':{'providerEventId':r['providerEventId'],'provider':r['source'],'checkedAtUtc':checked}});live+=1
  elif not match:events.append(r);added+=1;live+=int(r['tag']=='LIVE')
 p['events']=events;p['supplementalLiveAdapters']={'checkedAtUtc':checked,'diagnostics':diagnostics,'eventsAdded':added,'liveApplied':live};FEED.write_text(json.dumps(p,indent=2,ensure_ascii=False)+'\n')
if __name__=='__main__':main()
