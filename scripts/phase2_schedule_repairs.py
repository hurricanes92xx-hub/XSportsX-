#!/usr/bin/env python3
"""Phase 2 schedule repairs with Phase 1-style source and date safeguards."""
from __future__ import annotations
import json, re, urllib.request, subprocess, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; FEED=ROOT/'data/schedule_feed.json'; POLICY=ROOT/'data/schedule_season_policy.json'
HEADERS={'User-Agent':'XSportsX-Schedule/5.6','Accept':'application/json,text/html,*/*','Accept-Language':'en-US,en;q=0.9','Origin':'https://www.nba.com','Referer':'https://www.nba.com/'}
LOOKAHEAD_DAYS=370

def fetch(url,accept=None):
 h=dict(HEADERS)
 if accept:h['Accept']=accept
 with urllib.request.urlopen(urllib.request.Request(url,headers=h),timeout=30) as r:return r.read()
def get_json(url):return json.loads(fetch(url,'application/json,text/plain,*/*').decode('utf-8','ignore'))
def iso(v):
 if v is None:return None
 for s in (str(v).strip(),str(v).strip().replace('Z','+00:00'),str(v).strip().replace('z','+00:00')):
  try:return datetime.fromisoformat(s).astimezone(timezone.utc).isoformat().replace('+00:00','Z')
  except ValueError:pass
 return None
def add(events,league,title,start,source,icon):
 start=iso(start)
 if not start or not title:return False
 key=(league,title,start)
 if key in {(e.get('league'),e.get('title'),e.get('start')) for e in events}:return False
 events.append({'league':league,'title':title,'start':start,'tag':'UPCOMING','icon':icon,'source':source});return True
def window_ok(dt,league,policy,reference):
 if not(reference<=dt<=reference+timedelta(days=LOOKAHEAD_DAYS)):return False
 season=(policy.get('leagueWindows') or {}).get(league)
 if not season:return True
 md=(dt.month,dt.day); a=tuple(map(int,season[0])); b=tuple(map(int,season[1]))
 return a<=md<=b if a<=b else md>=a or md<=b
def valid_existing_or_added(events,league,policy,reference):
 out=[]
 for e in events:
  if e.get('league')!=league:continue
  dt=iso(e.get('start'))
  if dt and window_ok(datetime.fromisoformat(dt.replace('Z','+00:00')),league,policy,reference):out.append(dt)
 return out

def repair_nba(events,report,failures,policy,reference):
 urls=['https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json','https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json']
 parsed=added=0; source_used=None; errors=[]
 for url in urls:
  try:
   root=get_json(url); dates=((root.get('leagueSchedule') or {}).get('gameDates') or []) if isinstance(root,dict) else []
   rows=[g for d in dates for g in (d.get('games') or [])]
   if not rows:raise RuntimeError('schedule payload contained zero games')
   source_used=url; parsed=len(rows)
   for game in rows:
    start=game.get('gameDateTimeUTC') or game.get('gameDateTimeEst') or game.get('gameDate'); away=game.get('awayTeam') or {}; home=game.get('homeTeam') or {}
    an=away.get('teamName') or away.get('teamCity') or away.get('teamTricode'); hn=home.get('teamName') or home.get('teamCity') or home.get('teamTricode'); title=f'{an} @ {hn}' if an and hn else game.get('gameLabel') or 'NBA'
    if add(events,'NBA',title,start,'cdn.nba.com scheduleLeagueV2','🏀'):added+=1
   break
  except Exception as exc:errors.append(f'{url}: {exc}')
 valid=valid_existing_or_added(events,'NBA',policy,reference)
 report['NBA']={'source':'NBA official CDN scheduleLeagueV2','source_url':source_used,'parsed':parsed,'added':added,'current_future_existing_or_added':len(valid),'reference':reference.isoformat().replace('+00:00','Z'),'errors':errors}
 if valid:
  failures[:]=[x for x in failures if x!='NBA']; print(f'PHASE2 NBA: source healthy, parsed={parsed}, added={added}, current_future={len(valid)}')
 else:print(f'NO REPAIR NBA: parsed={parsed}, added={added}, current_future=0')

def probe_nll(events,report,failures,policy,reference):
 url='https://www.nll.com/schedule/full-schedule/'
 try:
  text=fetch(url,'text/html,*/*').decode('utf-8','ignore'); seasons=sorted(set(re.findall(r'20\d\d-\d\d',text))); pub='2026-27' in seasons; current=len(valid_existing_or_added(events,'NLL',policy,reference))
  report['NLL']={'source':'NLL official full schedule page','published_seasons':seasons,'2026_27_published':pub,'current_future_existing':current,'status':'awaiting_2026_27_publication' if not pub else 'published'}
  if pub and current:failures[:]=[x for x in failures if x!='NLL']
  print(f'PHASE2 NLL: published_2026_27={pub}, current_future_existing={current}')
 except Exception as exc:report['NLL']={'source':'NLL official full schedule page','status':'probe_failed','error':str(exc)};print(f'NO REPAIR NLL: {exc}')

def main():
 p=json.loads(FEED.read_text(encoding='utf-8')); events=p.get('events') or []; failures=list(p.get('officialSourceFailures') or []); policy=json.loads(POLICY.read_text(encoding='utf-8')) if POLICY.exists() else {}
 try:reference=datetime.fromisoformat(str(p.get('generatedAt')).replace('Z','+00:00')).astimezone(timezone.utc)
 except Exception:reference=datetime.now(timezone.utc)
 report=p.setdefault('phase2RepairReport',{}); repair_nba(events,report,failures,policy,reference); probe_nll(events,report,failures,policy,reference)
 p['events']=events;p['officialSourceFailures']=failures;p['eventCounts']={k:sum(1 for e in events if e.get('league')==k) for k in sorted({e.get('league') for e in events if e.get('league')})};p['generatedAt']=datetime.now(timezone.utc).isoformat();FEED.write_text(json.dumps(p,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print('PHASE2 failures remaining:',failures);print(f'PHASE2 complete: {len(events)} events across {len(p["eventCounts"])} leagues')
 # Phase 3 runs after all Phase 2 feed mutations and before the AAA guard/audit.
 # It only adds presentation metadata and never alters dates or event membership.
 subprocess.run([sys.executable, str(ROOT/'scripts'/'phase3_visual_enrichment.py')], check=True)
if __name__=='__main__':main()
