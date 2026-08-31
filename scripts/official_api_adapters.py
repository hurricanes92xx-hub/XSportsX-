#!/usr/bin/env python3
"""Official schedule adapters for leagues whose provider routes are unreliable.

These adapters are intentionally post-refresh and additive: they never delete
provider/preserved events. They add authoritative events when an official data
endpoint is available, then dedupe the combined feed.
"""
from __future__ import annotations
import json
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FEED=ROOT/'data'/'schedule_feed.json'
HEADERS={'User-Agent':'XSportsX-Schedule/3.0','Accept':'application/json,text/plain,*/*','Accept-Language':'en-US,en;q=0.9'}
NOW=datetime.now(timezone.utc)
HORIZON=NOW+timedelta(days=370)

NCAA=[
 ('NCAA BB','basketball-men','d1','🏀'),('NCAA WBB','basketball-women','d1','🏀'),
 ('NCAA Baseball','baseball','d1','⚾'),('NCAA Softball','softball','d1','🥎'),
 ("NCAA Men's Hockey",'icehockey-men','d1','🏒'),("NCAA Men's Soccer",'soccer-men','d1','⚽'),
 ("NCAA Women's Soccer",'soccer-women','d1','⚽'),("NCAA Men's Lacrosse",'lacrosse-men','d1','🥍'),
 ("NCAA Women's Lacrosse",'lacrosse-women','d1','🥍'),("NCAA Men's Volleyball",'volleyball-men','d1','🏐'),
 ("NCAA Women's Volleyball",'volleyball-women','d1','🏐'),("NCAA Men's Water Polo",'waterpolo-men','d1','🤽'),
 ("NCAA Women's Water Polo",'waterpolo-women','d1','🤽'),("NCAA Women's Field Hockey",'fieldhockey','d1','🏑'),
 ('NCAA Beach Volleyball','beach-volleyball','d1','🏐'),
]

def get_json(url):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=20) as r:return json.loads(r.read().decode('utf-8','ignore'))

def iso(value):
    if not value:return None
    text=str(value).strip()
    for candidate in (text,text.replace('Z','+00:00')):
        try:return datetime.fromisoformat(candidate).astimezone(timezone.utc).isoformat().replace('+00:00','Z')
        except ValueError:pass
    return None

def date_value(v):
    if isinstance(v,str):
        m=re.search(r'\d{4}-\d{2}-\d{2}',v)
        if m:return m.group(0)
    return None

def team_name(v):
    if isinstance(v,str):return v.strip()
    if isinstance(v,dict):
        for k in ('shortName','short','fullName','name','displayName','title'):
            if isinstance(v.get(k),str) and v[k].strip():return v[k].strip()
        names=v.get('names')
        if isinstance(names,dict):
            for k in ('short','full','medium'):
                if isinstance(names.get(k),str) and names[k].strip():return names[k].strip()
    return ''

def walk_ncaa(value,rows):
    if isinstance(value,dict):
        date=value.get('startDate') or value.get('date') or value.get('gameDate') or value.get('eventDate')
        dt=iso(value.get('startTime') or value.get('start') or value.get('startDateTime') or value.get('gameDateTime'))
        if not dt:
            d=date_value(date)
            if d:dt=d+'T00:00:00Z'
        away=team_name(value.get('away') or value.get('awayTeam') or value.get('visitor'))
        home=team_name(value.get('home') or value.get('homeTeam'))
        if dt and (away or home) and (NOW-timedelta(hours=12) <= datetime.fromisoformat(dt.replace('Z','+00:00')) <= HORIZON):
            rows.append((away,home,dt))
        for v in value.values():walk_ncaa(v,rows)
    elif isinstance(value,list):
        for v in value:walk_ncaa(v,rows)

def add_ncaa(events,report):
    year=NOW.year
    existing={(e.get('league'),e.get('title'),e.get('start')) for e in events}
    for league,sport,division,icon in NCAA:
        url=f'https://ncaa-api.henrygd.me/schedule-alt/{sport}/{division}/{year}'
        try:root=get_json(url)
        except Exception as exc:
            report.setdefault('ncaa',{})[league]=f'failed: {exc}'
            continue
        rows=[];walk_ncaa(root,rows); added=0
        for away,home,dt in rows:
            title=f'{away} @ {home}' if away and home else (home or away or league)
            key=(league,title,dt)
            if key in existing:continue
            events.append({'league':league,'title':title,'start':dt,'tag':'UPCOMING','icon':icon,'source':'official_api','sourceDetail':'NCAA schedule-alt'})
            existing.add(key);added+=1
        report.setdefault('ncaa',{})[league]=f'official_api:{added}'

def add_mlb(events,report):
    url=f'https://statsapi.mlb.com/api/v1/schedule?sportId=1&season={NOW.year}&startDate={NOW.date()}&endDate={HORIZON.date()}&hydrate=team,venue,broadcasts'
    try:root=get_json(url)
    except Exception as exc:
        report['MLB']=f'failed: {exc}';return
    existing={(e.get('league'),e.get('title'),e.get('start')) for e in events};added=0
    for day in root.get('dates',[]):
        for game in day.get('games',[]):
            dt=iso(game.get('gameDate'));teams=game.get('teams') or {}
            away=team_name((teams.get('away') or {}).get('team'));home=team_name((teams.get('home') or {}).get('team'))
            if not dt:continue
            status=((game.get('status') or {}).get('abstractGameState') or '').lower();tag='LIVE' if status=='live' else ('FINAL' if status=='final' else 'UPCOMING')
            title=f'{away} @ {home}' if away and home else 'MLB'
            key=('MLB',title,dt)
            if key in existing:continue
            events.append({'league':'MLB','title':title,'start':dt,'tag':tag,'icon':'⚾','source':'official_api','sourceDetail':'MLB Stats API'})
            existing.add(key);added+=1
    report['MLB']=f'official_api:{added}'

def main():
    payload=json.loads(FEED.read_text(encoding='utf-8'));events=payload.get('events') or [];report={}
    add_ncaa(events,report);add_mlb(events,report)
    unique={}
    for e in events:
        key=(e.get('league'),e.get('title'),e.get('start'))
        # Prefer official_api over provider/fallback for the same event.
        if key not in unique or str(e.get('source','')).startswith('official'):
            unique[key]=e
    payload['events']=list(unique.values())
    counts={}
    for e in payload['events']:counts[e.get('league','')]=counts.get(e.get('league',''),0)+1
    payload['eventCounts']=counts
    payload['officialApiAdapterReport']=report
    FEED.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('official API adapter report:',json.dumps(report,sort_keys=True))
    print(f'official API adapter total events: {len(payload["events"])}')
if __name__=='__main__':main()
