#!/usr/bin/env python3
"""Authoritative schedule adapters for sources whose web pages/providers are unreliable.

Adapters are additive: they never delete provider/preserved events.  Official
API events win during dedupe when the same event is present elsewhere.
"""
from __future__ import annotations
import json
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FEED=ROOT/'data'/'schedule_feed.json'
HEADERS={'User-Agent':'XSportsX-Schedule/4.0','Accept':'application/json,text/plain,*/*','Accept-Language':'en-US,en;q=0.9'}
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
 ('NCAA Beach Volleyball','beach-volleyball','nc','🏐'),
]

# NASCAR's documented Feed API uses 1=Cup, 2=XFINITY, 3=Truck.
NASCAR=[('NASCAR Cup',1,'🏁'),('NASCAR Xfinity',2,'🏁'),('NASCAR Truck',3,'🏁')]

def get_json(url):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=15) as r:
        return json.loads(r.read().decode('utf-8','ignore'))

def iso(value):
    if not value:return None
    text=str(value).strip()
    for candidate in (text,text.replace('Z','+00:00'),text.replace('z','+00:00')):
        try:return datetime.fromisoformat(candidate).astimezone(timezone.utc).isoformat().replace('+00:00','Z')
        except ValueError:pass
    # NCAA sometimes exposes a date plus a clock in separate fields; callers
    # handle that combination before reaching this function.
    return None

def date_value(v):
    if isinstance(v,str):
        m=re.search(r'\d{4}-\d{2}-\d{2}',v)
        if m:return m.group(0)
    return None

def team_name(v):
    if isinstance(v,str):return v.strip()
    if isinstance(v,dict):
        for k in ('shortName','short','fullName','full','displayName','name','title'):
            if isinstance(v.get(k),str) and v[k].strip():return v[k].strip()
        names=v.get('names')
        if isinstance(names,dict):
            for k in ('short','full','medium'):
                if isinstance(names.get(k),str) and names[k].strip():return names[k].strip()
    return ''

def parse_ncaa_time(value, date_hint=None):
    if isinstance(value,dict):
        for k in ('dateTime','datetime','startDateTime','startTime','date','startDate'):
            got=parse_ncaa_time(value.get(k),date_hint)
            if got:return got
        return None
    if value:
        got=iso(value)
        if got:return got
        text=str(value).strip()
        # Common API shape: 7:00PM ET with a separate YYYY-MM-DD date.
        d=date_value(text) or date_value(date_hint)
        m=re.search(r'(\d{1,2})(?::(\d{2}))?\s*([AP]M)',text,re.I)
        if d and m:
            hour=int(m.group(1)); minute=int(m.group(2) or 0); ampm=m.group(3).upper()
            if ampm=='PM' and hour!=12:hour+=12
            if ampm=='AM' and hour==12:hour=0
            return f'{d}T{hour:02d}:{minute:02d}:00Z'
        if d:return f'{d}T00:00:00Z'
    return None

def ncaa_rows(value, rows):
    """Extract contests from both schedule-alt GraphQL shapes and scoreboard-like shapes."""
    if isinstance(value,dict):
        date_hint=value.get('startDate') or value.get('date') or value.get('gameDate') or value.get('eventDate')
        dt=parse_ncaa_time(value.get('startDateTime') or value.get('startTime') or value.get('gameDateTime') or value.get('start') or date_hint,date_hint)
        teams=value.get('teams')
        away=team_name(value.get('away') or value.get('awayTeam') or value.get('visitor'))
        home=team_name(value.get('home') or value.get('homeTeam'))
        if isinstance(teams,list):
            named=[team_name(t.get('team') if isinstance(t,dict) and 'team' in t else t) for t in teams]
            named=[x for x in named if x]
            if len(named)>=2 and not (away or home):away,home=named[0],named[1]
        # GraphQL variants frequently put competitors/participants under a contest.
        competitors=value.get('competitors') or value.get('participants') or value.get('teams')
        if isinstance(competitors,list) and len(competitors)>=2 and not (away and home):
            named=[team_name(c.get('team') if isinstance(c,dict) and 'team' in c else c) for c in competitors]
            named=[x for x in named if x]
            if len(named)>=2:away,home=named[0],named[1]
        title=value.get('title') or value.get('name') or value.get('gameName') or value.get('eventName')
        if dt and (away or home or title):
            try:dt_obj=datetime.fromisoformat(dt.replace('Z','+00:00'))
            except ValueError:dt_obj=None
            if dt_obj and NOW-timedelta(hours=12) <= dt_obj <= HORIZON:
                if not (away or home) and isinstance(title,str):
                    title=title.strip()
                rows.append((away,home,dt,str(title or '').strip()))
        for v in value.values():ncaa_rows(v,rows)
    elif isinstance(value,list):
        for v in value:ncaa_rows(v,rows)

def add_ncaa(events,report):
    year=NOW.year
    existing={(e.get('league'),e.get('title'),e.get('start')) for e in events}
    for league,sport,division,icon in NCAA:
        url=f'https://ncaa-api.henrygd.me/schedule-alt/{sport}/{division}/{year}'
        try:root=get_json(url)
        except Exception as exc:
            report.setdefault('ncaa',{})[league]=f'failed: {exc}'
            continue
        rows=[];ncaa_rows(root,rows);added=0
        for away,home,dt,raw_title in rows:
            title=f'{away} @ {home}' if away and home else (raw_title or home or away or league)
            key=(league,title,dt)
            if key in existing:continue
            events.append({'league':league,'title':title,'start':dt,'tag':'UPCOMING','icon':icon,'source':'official_api','sourceDetail':'NCAA schedule-alt'})
            existing.add(key);added+=1
        report.setdefault('ncaa',{})[league]=f'official_api:{added}'

def add_nascar(events,report):
    existing={(e.get('league'),e.get('title'),e.get('start')) for e in events}
    for league,series_id,icon in NASCAR:
        url=f'https://feed.nascar.com/api/weekendschedule?series_id={series_id}&race_season={NOW.year}&v=1'
        try:root=get_json(url)
        except Exception as exc:
            report.setdefault('nascar',{})[league]=f'failed: {exc}'
            continue
        rows=root if isinstance(root,list) else (root.get('data') or root.get('schedule') or root.get('weekendSchedule') or [])
        if isinstance(rows,dict):rows=[rows]
        added=0
        for item in rows:
            if not isinstance(item,dict):continue
            dt=iso(item.get('start_time_utc') or item.get('startTimeUtc') or item.get('start_time') or item.get('startTime'))
            if not dt:continue
            try:dt_obj=datetime.fromisoformat(dt.replace('Z','+00:00'))
            except ValueError:continue
            if not NOW-timedelta(hours=12) <= dt_obj <= HORIZON:continue
            event_name=str(item.get('event_name') or item.get('eventName') or '').strip()
            race_name=str(item.get('race_name') or item.get('raceName') or '').strip()
            track=str(item.get('track_name') or item.get('trackName') or '').strip()
            run_type=item.get('run_type') or item.get('runType')
            kind={1:'Practice',2:'Qualifying',3:'Race'}.get(run_type,'Event')
            title=' — '.join(x for x in (race_name or event_name,kind,track if kind!='Race' else '') if x)
            if not title:title=league
            key=(league,title,dt)
            if key in existing:continue
            events.append({'league':league,'title':title,'start':dt,'tag':'UPCOMING','icon':icon,'source':'official_api','sourceDetail':'NASCAR Feed API'})
            existing.add(key);added+=1
        report.setdefault('nascar',{})[league]=f'official_api:{added}'

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
            title=f'{away} @ {home}' if away and home else 'MLB';key=('MLB',title,dt)
            if key in existing:continue
            events.append({'league':'MLB','title':title,'start':dt,'tag':tag,'icon':'⚾','source':'official_api','sourceDetail':'MLB Stats API'});existing.add(key);added+=1
    report['MLB']=f'official_api:{added}'

def main():
    payload=json.loads(FEED.read_text(encoding='utf-8'));events=payload.get('events') or [];report={}
    add_ncaa(events,report);add_nascar(events,report);add_mlb(events,report)
    unique={}
    for e in events:
        key=(e.get('league'),e.get('title'),e.get('start'))
        if key not in unique or str(e.get('source','')).startswith('official'):unique[key]=e
    payload['events']=list(unique.values())
    counts={}
    for e in payload['events']:counts[e.get('league','')]=counts.get(e.get('league',''),0)+1
    payload['eventCounts']=counts;payload['officialApiAdapterReport']=report
    FEED.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('official API adapter report:',json.dumps(report,sort_keys=True));print(f'official API adapter total events: {len(payload["events"])}')
if __name__=='__main__':main()
