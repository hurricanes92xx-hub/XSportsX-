#!/usr/bin/env python3
"""Guarded official WWE/AEW recurring schedule repair."""
from __future__ import annotations
import json,re,urllib.request
from datetime import datetime,timezone,timedelta
from html.parser import HTMLParser
from pathlib import Path
FEED=Path('data/schedule_feed.json'); LOOKAHEAD=370
HEADERS={'User-Agent':'XSportsX-Schedule/5.6','Accept':'text/html,application/json,*/*','Accept-Language':'en-US,en;q=0.9'}
class T(HTMLParser):
 def __init__(self): super().__init__(); self.parts=[]
 def handle_data(self,d):
  d=' '.join(d.split())
  if d:self.parts.append(d)
 def text(self): return ' '.join(self.parts)
def fetch(u):
 with urllib.request.urlopen(urllib.request.Request(u,headers=HEADERS),timeout=30) as r:return r.read().decode('utf-8','ignore')
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
  try: out += json.loads(b) if isinstance(json.loads(b),list) else [json.loads(b)]
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
def repair(league,url,events,report,failures,ref):
 try:
  h=fetch(url); rows=[]
  for o in objs(jsonld(h)):
   d=dt(o.get('startDate'))
   if d and ref<=d<=ref+timedelta(days=LOOKAHEAD):rows.append((o.get('name') or o.get('headline') or league,d))
  if not rows:
   p=T();p.feed(h);s=p.text()
   # Only consume dates actually published on the official page; never synthesize cadence.
   rx=r'\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+([A-Z][a-z]+\.?\s+\d{1,2},\s+202\d)'
   for x in re.findall(rx,s):
    try:d=datetime.strptime(x.replace('.',''),'%B %d, %Y').replace(tzinfo=timezone.utc)
    except ValueError:continue
    if ref<=d<=ref+timedelta(days=LOOKAHEAD):
     low=s[max(0,s.find(x)-180):s.find(x)+180].lower(); title=league
     for k,n in [('smackdown','SmackDown'),('raw','Raw'),('nxt','NXT'),('evolve','Evolve'),('main event','Main Event'),('dynamite/​collision','Dynamite/Collision'),('dynamite','Dynamite'),('collision','Collision')]:
      if k in low:title=f'{league} {n}';break
     rows.append((title,d))
  added=sum(add(events,league,n,d,url) for n,d in rows)
  valid=[e for e in events if e.get('league')==league and (x:=dt(e.get('start'))) and ref<=x<=ref+timedelta(days=LOOKAHEAD)]
  weekly=sum(1 for e in valid if any(k in (e.get('title') or '').lower() for k in ('raw','smackdown','nxt','evolve','main event','dynamite','collision')))
  report[league]={'source':url,'parsed_official_events':len(rows),'added':added,'current_future_existing_or_added':len(valid),'weekly_show_events':weekly,'validated':bool(valid)}
  if valid:failures[:]=[x for x in failures if x!=league];print(f'REPAIRED {league}: official_dated={len(rows)} added={added} current_future={len(valid)} weekly={weekly}')
  else:print(f'NO REPAIR {league}: no valid future official events')
 except Exception as e:report[league]={'source':url,'validated':False,'error':str(e)};print(f'NO REPAIR {league}: {e}')
def main():
 p=json.loads(FEED.read_text());events=p.get('events') or [];failures=list(p.get('officialSourceFailures') or []);report=p.setdefault('providerRepairReport',{})
 try:ref=datetime.fromisoformat(str(p.get('generatedAt')).replace('Z','+00:00')).astimezone(timezone.utc)
 except Exception:ref=datetime.now(timezone.utc)
 repair('WWE','https://www.wwe.com/article/wwe-upcoming-events',events,report,failures,ref)
 repair('AEW','https://www.allelitewrestling.com/aew-events/full-gear-2025',events,report,failures,ref)
 p['events']=events;p['officialSourceFailures']=failures;p['eventCounts']={k:sum(1 for e in events if e.get('league')==k) for k in sorted({e.get('league') for e in events if e.get('league')})};p['generatedAt']=datetime.now(timezone.utc).isoformat();FEED.write_text(json.dumps(p,indent=2,ensure_ascii=False)+'\n')
if __name__=='__main__':main()
