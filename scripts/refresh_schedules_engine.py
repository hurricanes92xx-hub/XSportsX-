#!/usr/bin/env python3
"""Run the canonical publisher through bounded, rate-limited, season-aware access."""
from __future__ import annotations
import importlib.util,json,re,threading,time,urllib.parse,urllib.request,sys
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path); module=importlib.util.module_from_spec(spec); assert spec.loader is not None; sys.modules[name]=module; spec.loader.exec_module(module); return module
refresh=load('xsportsx_refresh',ROOT/'scripts'/'refresh_schedules.py'); engine=load('xsportsx_schedule_engine_safe',ROOT/'scripts'/'schedule_engine_safe.py'); season=load('xsportsx_season_intelligence',ROOT/'scripts'/'season_intelligence.py')
MAX_CONCURRENT=8; semaphore=threading.BoundedSemaphore(MAX_CONCURRENT); guards={}; guards_lock=threading.Lock()
DEDICATED_OFFICIAL={'NASCAR Cup','NASCAR Xfinity','NASCAR Truck'}
DEDICATED_NCAA={'NCAA BB','NCAA WBB','NCAA Baseball','NCAA Softball',"NCAA Men's Hockey","NCAA Men's Soccer","NCAA Women's Soccer","NCAA Men's Lacrosse","NCAA Women's Lacrosse","NCAA Men's Volleyball","NCAA Women's Volleyball","NCAA Men's Water Polo","NCAA Women's Water Polo","NCAA Women's Field Hockey",'NCAA Beach Volleyball','NCAA FCS'}
DISABLED_LEAGUES={'ACTION SPORTS','ESPORTS','ESPORTS - ROCKET LEAGUE','ESPORTS - APEX LEGENDS','ESPORTS - RAINBOW SIX'}
def guard_for(url):
 host=urllib.parse.urlsplit(url).netloc.lower() or 'unknown'
 with guards_lock:return guards.setdefault(host,engine.SourceGuard())
def guarded_get(url):
 guard=guard_for(url); last=None
 for attempt in range(1,5):
  guard.wait_turn()
  with semaphore:
   try:
    req=urllib.request.Request(url,headers=refresh.HEADERS)
    with urllib.request.urlopen(req,timeout=12) as response:data=response.read()
    guard.success();return data
   except Exception as exc:
    last=exc;guard.failure()
    if attempt>=4:raise
    time.sleep(engine.backoff_seconds(attempt))
 raise last
def previous_root():
 try:return json.loads((ROOT/'data/schedule_feed.json').read_text(encoding='utf-8'))
 except Exception:return {}
PREVIOUS_ROOT=previous_root();PREVIOUS=PREVIOUS_ROOT.get('events') or [];SEASON_REPORT=[]
def preserved(events,league):
 rows=[e for e in PREVIOUS if e.get('league')==league];events.extend(rows);return len(rows)
def decision_for(name):return season.analyze(name,PREVIOUS)
def _iso(value):
 if not value:return None
 try:return datetime.fromisoformat(str(value).replace('Z','+00:00')).astimezone(timezone.utc)
 except Exception:return None
def _normalize_timestamp(value):
 if value is None:return None
 text=str(value).strip()
 if not text:return None
 for candidate in (text,text.replace('Z','+00:00'),text.replace('z','+00:00')):
  try:return datetime.fromisoformat(candidate).astimezone(timezone.utc).isoformat().replace('+00:00','Z')
  except ValueError:pass
 for fmt in ('%m/%d/%YT%H:%M:%SZ','%m/%d/%YT%H:%M:%S%z','%m/%d/%YT%H:%M:%S','%m/%d/%Y %H:%M:%S','%m/%d/%Y'):
  try:
   dt=datetime.strptime(text,fmt)
   if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
   return dt.astimezone(timezone.utc).isoformat().replace('+00:00','Z')
  except ValueError:pass
 return None
def normalize_feed_timestamps(payload):
 invalid=[];changed=0
 for event in payload.get('events') or []:
  raw=event.get('start');normalized=_normalize_timestamp(raw)
  if normalized is None:invalid.append(event);continue
  if raw!=normalized:event['start']=normalized;changed+=1
 return changed,invalid
def _embedded_json_documents(html):
 text=html.decode('utf-8','ignore') if isinstance(html,(bytes,bytearray)) else str(html)
 patterns=[r'<script[^>]+type=["\']application/json["\'][^>]*>(.*?)</script>',r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>']
 for pattern in patterns:
  for m in re.findall(pattern,text,re.I|re.S):
   try:yield json.loads(m.strip())
   except Exception:continue
def _walk_official_events(value,league,events,seen,now,horizon):
 if isinstance(value,dict):
  name=value.get('name') or value.get('eventName') or value.get('title');date=value.get('startDate') or value.get('start') or value.get('startTime') or value.get('date');typ=value.get('@type');is_event=typ=='Event' or (isinstance(typ,list) and 'Event' in typ);dt=_iso(date)
  if name and dt and (is_event or ('schedule' in str(value).lower() and 'date' in str(value).lower())) and now<=dt<=horizon:
   key=(league,str(name).strip(),dt.isoformat())
   if key not in seen:seen.add(key);events.append({'league':league,'title':str(name).strip(),'start':dt.isoformat().replace('+00:00','Z'),'tag':'UPCOMING','icon':'🏆','source':'official'})
  for v in value.values():_walk_official_events(v,league,events,seen,now,horizon)
 elif isinstance(value,list):
  for v in value:_walk_official_events(v,league,events,seen,now,horizon)
def official_embedded_fallback(events,source):
 name=str(source.get('league') or '').strip();urls=source.get('urls') or [source.get('url')];urls=[str(u).strip() for u in urls if str(u or '').strip()]
 if not name or not urls:return False,0
 before=len(events);seen={(e.get('league'),e.get('title'),e.get('start')) for e in events};now=datetime.now(timezone.utc)-timedelta(hours=12);horizon=datetime.now(timezone.utc)+timedelta(days=370);successful=False
 for url in urls:
  try:raw=guarded_get(url);successful=True
  except Exception as exc:print(f'ERROR official embedded {name} {url}: {exc}');continue
  for doc in _embedded_json_documents(raw):_walk_official_events(doc,name,events,seen,now,horizon)
  if len(events)>before:break
 return successful,len(events)-before
_original_add_official=refresh.add_official_source;_original_add_espn=refresh.add_espn;_original_add_ncaa=refresh.add_ncaa
def season_aware_official(events,source):
 name=str(source.get('league') or '').strip()
 if name.upper() in DISABLED_LEAGUES:return True,0
 if name in DEDICATED_OFFICIAL or name in DEDICATED_NCAA:print(f'INFO dedicated adapter owns {name}; skipping legacy official source');return True,0
 d=decision_for(name);SEASON_REPORT.append(d|{'provider':'official'})
 if name and not d['active']:
  generated=PREVIOUS_ROOT.get('generatedAt','');last=None
  try:last=datetime.fromisoformat(str(generated).replace('Z','+00:00'))
  except Exception:pass
  age=(datetime.now(timezone.utc)-last).total_seconds()/3600 if last else 999
  if age<d['probeHours']:return True,preserved(events,name)
 ok,n=_original_add_official(events,source)
 if ok and n:return True,n
 eok,en=official_embedded_fallback(events,source)
 if en:return True,en
 preserved_count=preserved(events,name) if name else 0
 print(f'WARNING official source unavailable for {name}; preserved {preserved_count} prior events')
 return False if not preserved_count else True,preserved_count
def season_aware_espn(events,name,sport,league,icon,days):
 if name.upper() in DISABLED_LEAGUES:return True,0
 if name in DEDICATED_OFFICIAL:print(f'INFO dedicated adapter owns {name}; skipping legacy ESPN source');return True,0
 d=decision_for(name);SEASON_REPORT.append(d|{'provider':'espn'})
 if not d['active']:return True,preserved(events,name)
 return _original_add_espn(events,name,sport,league,icon,days)
def season_aware_ncaa(events,name,sport,division,icon,days=30):
 if name in DEDICATED_NCAA:print(f'INFO dedicated adapter owns {name}; skipping legacy NCAA source');return True,0
 d=decision_for(name);SEASON_REPORT.append(d|{'provider':'ncaa'})
 if not d['active']:return True,preserved(events,name)
 ok,n=_original_add_ncaa(events,name,sport,division,icon,days)
 if ok and n:return ok,n
 preserved_count=preserved(events,name)
 if preserved_count:print(f'WARNING NCAA source unavailable for {name}; preserved {preserved_count} prior events');return True,preserved_count
 return ok,n
refresh.get=guarded_get;refresh.add_official_source=season_aware_official;refresh.add_espn=season_aware_espn;refresh.add_ncaa=season_aware_ncaa
refresh.main()
feed=ROOT/'data/schedule_feed.json'
try:
 payload=json.loads(feed.read_text(encoding='utf-8'))
 disabled=DISABLED_LEAGUES
 payload['events']=[e for e in payload.get('events') or [] if str(e.get('league','')).upper() not in disabled]
 payload['eventCounts']={k:sum(1 for e in payload['events'] if e.get('league')==k) for k in sorted({e.get('league') for e in payload['events'] if e.get('league')})}
 payload['failedSources']=[x for x in payload.get('failedSources',[]) if str(x).upper() not in disabled]
 payload['officialSourceFailures']=[x for x in payload.get('officialSourceFailures',[]) if str(x).upper() not in disabled]
 changed,invalid=normalize_feed_timestamps(payload);print(f'normalized {changed} schedule timestamps')
 if invalid:print(f'WARNING could not normalize {len(invalid)} schedule timestamps')
 payload['seasonIntelligence']={'generatedAt':datetime.now(timezone.utc).isoformat(),'mode':'calendar_plus_observed_activity','providerDecisions':SEASON_REPORT}
 tmp=feed.with_suffix('.tmp');tmp.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');tmp.replace(feed)
except Exception as exc:print(f'WARNING season intelligence metadata: {exc}')
