#!/usr/bin/env python3
"""Guarded official WWE/AEW recurring schedule repair."""
from __future__ import annotations
import json,re,time,urllib.error,urllib.request
from datetime import datetime,timezone,timedelta
from html.parser import HTMLParser
from pathlib import Path
FEED=Path('data/schedule_feed.json'); LOOKAHEAD=370
HEADERS={'User-Agent':'XSportsX-Schedule/5.6 (+schedule refresh)','Accept':'text/html,application/xhtml+xml,application/json,*/*','Accept-Language':'en-US,en;q=0.9','Cache-Control':'no-cache'}
WWE_WEEKLY=('raw','nxt','evolve','main event','smackdown','monday night raw','friday night smackdown','saturday night main event')
AEW_WEEKLY=('dynamite','collision')
class T(HTMLParser):
 def __init__(self): super().__init__(); self.parts=[]
 def handle_data(self,d):
  d=' '.join(d.split())
  if d:self.parts.append(d)
 def text(self): return ' '.join(self.parts)
def fetch(u,retries=3):
 last=None
 for attempt in range(retries):
  try:
   req=urllib.request.Request(u,headers=HEADERS)
   with urllib.request.urlopen(req,timeout=30) as r:return r.read().decode('utf-8','ignore')
  except urllib.error.HTTPError as e:
   last=e
   if e.code not in (429,500,502,503,504): raise
   if attempt+1<retries: time.sleep(2**attempt)
  except Exception as e:
   last=e
   if attempt+1<retries: time.sleep(2**attempt)
 if last: raise last
 raise RuntimeError(f'failed to fetch {u}')
def dt(v):
 try:return datetime.fromisoformat(str(v).replace('Z','+00:00')).astimezone(timezone.utc)
 except Exception:return None
def add(events,league,title,d,source):
 d=dt(d)
 if not d or not title:return False
 s=d.isoformat().replace('+00:00','Z'); key=(league,title,s)
 if key in {(e.get('league'),e.get('title'),e.get('start')) for e in events}:return False
 events.append({'league':league,'title':title,'start':s,'tag':'UPCOMING','icon':'🤼','source':source}); return True
def jsonld(h):
 out=[]
 for b in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',h,re.I|re.S):
  try:
   x=json.loads(b); out += x if isinstance(x,list) else [x]
  except Exception: pass
 return out
def objs(xs):
 out=[]
 def w(x):
  if isinstance(x,dict):
   if x.get('startDate') or 'Event' in str(x.get('@type','')):out.append(x)
   for v in x.values():
    if isinstance(v,(dict,list)):w(v)
  elif isinstance(x,list):
   for v in x:w(v)
 for x in xs:w(x)
 return out
def parse_official(h,league,ref):
 rows=[]
 for o in objs(jsonld(h)):
  d=dt(o.get('startDate')); name=o.get('name') or o.get('headline') or league
  if d and ref<=d<=ref+timedelta(days=LOOKAHEAD):rows.append((name,d))
 if rows:return rows
 p=T();p.feed(h);s=p.text()
 rx=r'\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+([A-Z][a-z]+\.?\s+\d{1,2},\s+202\d)'
 for x in re.findall(rx,s):
  try:d=datetime.strptime(x.replace('.',''),'%B %d, %Y').replace(tzinfo=timezone.utc)
  except ValueError:continue
  if ref<=d<=ref+timedelta(days=LOOKAHEAD):
   low=s[max(0,s.find(x)-180):s.find(x)+180].lower(); title=league
   for k,n in [('raw','Raw'),('smackdown','SmackDown'),('nxt','NXT'),('evolve','Evolve'),('main event','Main Event'),('dynamite/\u200bcollision','Dynamite/Collision'),('dynamite/collision','Dynamite/Collision'),('dynamite','Dynamite'),('collision','Collision')]:
    if k in low:title=f'{league} {n}';break
   rows.append((title,d))
 return rows
def parse_fallback(h,league,ref):
 rows=[]
 for o in objs(jsonld(h)):
  d=dt(o.get('startDate')); name=str(o.get('name') or o.get('headline') or '')
  if d and ref<=d<=ref+timedelta(days=LOOKAHEAD) and any(k in name.lower() for k in ('aew','dynamite','collision','wrestledream','all out','full gear','grand slam','revolution','double or nothing','forbidden door','all in')):
   rows.append((name,d))
 if rows:return rows
 p=T();p.feed(h);s=p.text(); rx=r'([A-Z][a-z]+\s+\d{1,2},\s+202\d)'
 for x in re.findall(rx,s):
  try:d=datetime.strptime(x,'%B %d, %Y').replace(tzinfo=timezone.utc)
  except ValueError:continue
  if not (ref<=d<=ref+timedelta(days=LOOKAHEAD)):continue
  pos=s.find(x); low=s[max(0,pos-160):pos+180].lower()
  if not any(k in low for k in ('aew','dynamite','collision','wrestledream','all out','full gear','grand slam','revolution','double or nothing','forbidden door','all in')):continue
  title='AEW Event'
  for k,n in [('dynamite/collision','Dynamite/Collision'),('dynamite','Dynamite'),('collision','Collision')]:
   if k in low:title=f'AEW {n}';break
  rows.append((title,d))
 return rows
def weekly_count(league,valid):
 keys=WWE_WEEKLY if league=='WWE' else AEW_WEEKLY
 return sum(1 for e in valid if any(k in (e.get('title') or '').lower() for k in keys))
def repair(league,url,events,report,failures,ref,fallback_url=None):
 try:
  h=fetch(url); rows=parse_official(h,league,ref); source=url
  if not rows and fallback_url:
   h=fetch(fallback_url); rows=parse_fallback(h,league,ref); source=fallback_url
  if not rows:raise RuntimeError('no valid future official events')
  added=sum(add(events,league,n,d,source) for n,d in rows)
  valid=[e for e in events if e.get('league')==league and (x:=dt(e.get('start'))) and ref<=x<=ref+timedelta(days=LOOKAHEAD)]
  weekly=weekly_count(league,valid)
  report[league]={'source':source,'parsed_official_events':len(rows),'added':added,'current_future_existing_or_added':len(valid),'weekly_show_events':weekly,'validated':bool(valid),'fallback_used':source!=url}
  if valid:failures[:]=[x for x in failures if x!=league];print(f'REPAIRED {league}: source={source} official_dated={len(rows)} added={added} current_future={len(valid)} weekly={weekly}')
  else:print(f'NO REPAIR {league}: no valid future events')
 except Exception as e:
  if fallback_url and url!=fallback_url:
   try:
    h=fetch(fallback_url); rows=parse_fallback(h,league,ref); added=sum(add(events,league,n,d,fallback_url) for n,d in rows)
    valid=[e for e in events if e.get('league')==league and (x:=dt(e.get('start'))) and ref<=x<=ref+timedelta(days=LOOKAHEAD)]; weekly=weekly_count(league,valid)
    report[league]={'source':fallback_url,'official_source':url,'parsed_official_events':len(rows),'added':added,'current_future_existing_or_added':len(valid),'weekly_show_events':weekly,'validated':bool(valid),'fallback_used':True,'official_error':str(e)}
    if valid:failures[:]=[x for x in failures if x!=league];print(f'REPAIRED {league}: fallback source={fallback_url} parsed={len(rows)} added={added} current_future={len(valid)} weekly={weekly}')
    else:print(f'NO REPAIR {league}: fallback returned no valid future events')
    return
   except Exception as fe:e=f'{e}; fallback={fe}'
  report[league]={'source':url,'validated':False,'error':str(e)};print(f'NO REPAIR {league}: {e}')
def main():
 p=json.loads(FEED.read_text());events=p.get('events') or [];failures=list(p.get('officialSourceFailures') or []);report=p.setdefault('providerRepairReport',{})
 try:ref=datetime.fromisoformat(str(p.get('generatedAt')).replace('Z','+00:00')).astimezone(timezone.utc)
 except Exception:ref=datetime.now(timezone.utc)
 repair('WWE','https://www.wwe.com/article/wwe-upcoming-events',events,report,failures,ref)
 repair('AEW','https://www.allelitewrestling.com/aew-events/full-gear-2025',events,report,failures,ref,'https://www.sync2cal.com/sports/fighting/aew')
 p['events']=events;p['officialSourceFailures']=failures;p['eventCounts']={k:sum(1 for e in events if e.get('league')==k) for k in sorted({e.get('league') for e in events if e.get('league')})};p['generatedAt']=datetime.now(timezone.utc).isoformat();FEED.write_text(json.dumps(p,indent=2,ensure_ascii=False)+'\n')
if __name__=='__main__':main()
