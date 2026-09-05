#!/usr/bin/env python3
"""Parse the public X Games event pages into canonical schedule events."""
from __future__ import annotations
import json,re,html,urllib.request
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; FEED=ROOT/'data'/'schedule_feed.json'; UA='XSportsX-XGamesOfficial/1.0'
PAGES=(
 ('https://www.xgames.com/events/sacramento-2026/','X Games Sacramento 2026'),
 ('https://www.xgames.com/events/japan-2026-2/','X Games Chiba 2026'),
 ('https://www.xgames.com/events/new-orleans-2026/','X Games New Orleans 2026'),
 ('https://www.xgames.com/events/aspen-2026/','X Games Aspen 2026'),
 ('https://www.xgames.com/','XGL Winter Draft 2026'),
)
MONTHS='January February March April May June July August September October November December'.split()
MONTH_RE='|'.join(MONTHS)
TZ={'PST':-8,'PDT':-7,'MST':-7,'MDT':-6,'CST':-6,'CDT':-5,'EST':-5,'EDT':-4,'JST':9}
def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml,*/*'})
 with urllib.request.urlopen(req,timeout=15) as r:return r.read().decode('utf-8','ignore')
def iso_date_time(date_s,time_s,tz_s,year=2026):
 try:
  mon,day=re.match(rf'({MONTH_RE})\s+(\d{{1,2}})',date_s,re.I).groups(); h,m=re.match(r'(\d{1,2}):(\d{2})',time_s).groups(); ap=time_s[-2:].upper(); h=int(h);m=int(m)
  if ap=='PM' and h<12:h+=12
  if ap=='AM' and h==12:h=0
  off=TZ.get(tz_s.upper(),0);dt=datetime(year,MONTHS.index(mon.title())+1,int(day),h,m,tzinfo=timezone(timedelta(hours=off)));return dt.astimezone(timezone.utc).isoformat().replace('+00:00','Z')
 except Exception:return ''
def clean_text(s):
 s=html.unescape(s);s=re.sub(r'<script\b.*?</script>',' ',s,flags=re.I|re.S);s=re.sub(r'<style\b.*?</style>',' ',s,flags=re.I|re.S);s=re.sub(r'<[^>]+>','\n',s);s=s.replace('\r','\n');return '\n'.join(x.strip() for x in s.split('\n') if x.strip())
def parse_page(url,label):
 raw=fetch(url);text=clean_text(raw);rows=[]
 # Server-rendered X Games pages expose schedule rows as: Date | time-time TZ Event.
 pat=re.compile(rf'(?P<date>{MONTH_RE}\s+\d{{1,2}})\s*\|\s*(?P<time>\d{{1,2}}:\d{{2}}\s*(?:AM|PM)?(?:\s*[–-]\s*\d{{1,2}}:\d{{2}}\s*(?:AM|PM)?)?)\s*(?P<tz>[A-Z]{{2,4}})\s*(?P<event>[^\n|]+)',re.I)
 for m in pat.finditer(text):
  event=m.group('event').strip(' -*');
  if not re.search(r'BMX|Skate|SKB|Moto|Scooter|Snow|Ski|XGL|Draft',event,re.I):continue
  tm=m.group('time');start_tm=re.search(r'\d{1,2}:\d{2}\s*(?:AM|PM)',tm,re.I)
  if not start_tm:continue
  start=iso_date_time(m.group('date'),start_tm.group(),m.group('tz')); 
  if not start:continue
  rows.append({'league':'X Games','sport':'X Games','title':event,'start':start,'startUtc':start,'tag':'UPCOMING','status':'UPCOMING','state':'pre','source':'xgames-official','providerEventId':f"xgames:{re.sub(r'[^a-z0-9]+','-',label.lower()).strip('-')}:{start}:{re.sub(r'[^a-z0-9]+','-',event.lower()).strip('-')}",'officialSourceUrl':url})
 # Homepage currently exposes the Winter Draft as a card rather than a schedule table.
 if 'winter draft' in text.lower():
  m=re.search(r'XGL Winter Draft 2026.*?(September\s+\d{1,2},\s*2026)',text,re.I|re.S)
  if m:
   d=datetime.strptime(m.group(1),'%B %d, %Y').replace(hour=19,tzinfo=timezone.utc)
   rows.append({'league':'X Games','sport':'X Games','title':'XGL Winter Draft 2026','start':d.isoformat().replace('+00:00','Z'),'startUtc':d.isoformat().replace('+00:00','Z'),'tag':'UPCOMING','status':'UPCOMING','state':'pre','source':'xgames-official','providerEventId':'xgames:xgl-winter-draft-2026','officialSourceUrl':url})
 return rows

def main():
 payload=json.loads(FEED.read_text());events=[e for e in payload.get('events',[]) if isinstance(e,dict)];diag={'status':'ok','pages':0,'events':0,'errors':[]};added=0
 for url,label in PAGES:
  try:
   rows=parse_page(url,label);diag['pages']+=1;diag['events']+=len(rows)
   for r in rows:
    key=(str(r.get('providerEventId')),str(r.get('startUtc')))
    if any((str(e.get('providerEventId')),str(e.get('startUtc'))) == key for e in events):continue
    events.append(r);added+=1
  except Exception as e:diag['errors'].append(f'{label}:{type(e).__name__}:{str(e)[:160]}')
 if not diag['events'] and diag['errors']:diag['status']='unavailable'
 payload['events']=events;payload['xgamesOfficialAdapter']={'checkedAtUtc':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'diagnostics':diag,'eventsAdded':added};FEED.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n')
if __name__=='__main__':main()
