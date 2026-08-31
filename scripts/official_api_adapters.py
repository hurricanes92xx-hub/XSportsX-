#!/usr/bin/env python3
"""Authoritative schedule adapters for sources whose web pages/providers are unreliable.

Adapters are additive: they never delete provider/preserved events. Official API
schedule data wins during dedupe when the same event is present elsewhere.
"""
from __future__ import annotations
import json
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FEED=ROOT/'data'/'schedule_feed.json'
HEADERS={'User-Agent':'XSportsX-Schedule/5.0','Accept':'application/json,text/plain,*/*','Accept-Language':'en-US,en;q=0.9'}
NOW=datetime.now(timezone.utc)
HORIZON=NOW+timedelta(days=370)

NCAA=[
 ('NCAA BB','basketball-men','d1','🏀'),('NCAA WBB','basketball-women','d1','🏀'),
 ('NCAA Baseball','baseball','d1','⚾'),('NCAA Softball','softball','d1','🥎'),
 ("NCAA Men's Hockey",'icehockey-men','d1','🏒'),("NCAA Men's Soccer",'soccer-men','d1','⚽'),
 ("NCAA Women's Soccer",'soccer-women','d1','⚽'),("NCAA Men's Lacrosse",'lacrosse-men','d1','🥍'),
 ("NCAA Women's Lacrosse",'lacrosse-women','d1','🥍'),("NCAA Men's Volleyball",'volleyball-men','d1','🏐'),
 ("NCAA Women's Volleyball",'volleyball-women','d1','🏐'),("NCAA Men's Water Polo",'waterpolo-men','d1','🤽'),
 ("NCAA Women's Water Polo",'waterpolo-women','d1','🤽'),("NCAA Women's Field Hockey",'fieldhockey-women','d1','🏑'),
 ('NCAA Beach Volleyball','beach-volleyball','d1','🏐'),
]
NASCAR=[('NASCAR Cup',1,'🏁'),('NASCAR Xfinity',2,'🏁'),('NASCAR Truck',3,'🏁')]

def get_json(url):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=20) as r:
        return json.loads(r.read().decode('utf-8','ignore'))

def iso(value):
    if value is None:return None
    if isinstance(value,(int,float)):
        # Accept Unix seconds or milliseconds when the upstream GraphQL source uses epochs.
        try:
            seconds=float(value)/1000 if float(value)>10_000_000_000 else float(value)
            return datetime.fromtimestamp(seconds,tz=timezone.utc).isoformat().replace('+00:00','Z')
        except Exception:return None
    text=str(value).strip()
    if not text:return None
    for candidate in (text,text.replace('Z','+00:00'),text.replace('z','+00:00')):
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
        for k in ('shortName','short','displayName','fullName','full','name','title','teamName'):
            if isinstance(v.get(k),str) and v[k].strip():return v[k].strip()
        names=v.get('names')
        if isinstance(names,dict):
            for k in ('short','full','medium','char6'):
                if isinstance(names.get(k),str) and names[k].strip():return names[k].strip()
    return ''

def parse_clock(text,date_hint=None):
    if not text:return None
    d=date_value(text) or date_value(date_hint)
    m=re.search(r'(\d{1,2})(?::(\d{2}))?(?::(\d{2}))?\s*([AP]M)(?:\s*[A-Z]{2,4})?',str(text),re.I)
    if d and m:
        hour=int(m.group(1)); minute=int(m.group(2) or 0); second=int(m.group(3) or 0); ampm=m.group(4).upper()
        if ampm=='PM' and hour!=12:hour+=12
        if ampm=='AM' and hour==12:hour=0
        return f'{d}T{hour:02d}:{minute:02d}:{second:02d}Z'
    return None

def parse_ncaa_time(value,date_hint=None):
    if isinstance(value,dict):
        for k in ('dateTime','datetime','startDateTimeUtc','startDateTime','scheduledStartTime','startTime','date','startDate','gameDate'):
            got=parse_ncaa_time(value.get(k),date_hint or value.get('date') or value.get('startDate'))
            if got:return got
        return None
    got=iso(value)
    if got:return got
    return parse_clock(value,date_hint)

def ncaa_rows(value,rows):
    """Extract contests from the current NCAA GraphQL schedule-alt response.

    The public wrapper deliberately returns raw upstream data, whose field names
    have changed between releases. Walk it recursively and accept the common
    contest/team/date variants instead of assuming one response shape.
    """
    if isinstance(value,dict):
        date_hint=(value.get('startDate') or value.get('gameDate') or value.get('eventDate') or
                   value.get('date') or value.get('scheduledDate'))
        dt=None
        for k in ('startDateTimeUtc','startDateTime','scheduledStartTime','gameDateTime','start','startTime','dateTime','date'):
            if k in value:
                dt=parse_ncaa_time(value.get(k),date_hint)
                if dt:break
        away=team_name(value.get('away') or value.get('awayTeam') or value.get('visitor') or value.get('visitingTeam'))
        home=team_name(value.get('home') or value.get('homeTeam') or value.get('host') or value.get('homeParticipant'))
        competitors=value.get('competitors') or value.get('participants') or value.get('teams')
        if isinstance(competitors,list) and len(competitors)>=2:
            named=[team_name(c.get('team') if isinstance(c,dict) and 'team' in c else c) for c in competitors]
            named=[x for x in named if x]
            if len(named)>=2 and not (away and home):away,home=named[0],named[1]
        title=value.get('title') or value.get('name') or value.get('gameName') or value.get('eventName') or value.get('contestName')
        if dt and (away or home or title):
            try:dt_obj=datetime.fromisoformat(dt.replace('Z','+00:00'))
            except ValueError:dt_obj=None
            if dt_obj and NOW-timedelta(hours=12) <= dt_obj <= HORIZON:
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
        if added==0:
            # Make the failure visible without making the whole workflow fail.
            print(f'WARNING NCAA adapter returned zero normalized events for {league}')

def nascar_races(root,series_id):
    rows=[]
    def walk(value,context=None):
        if isinstance(value,dict):
            sid=value.get('series_id') or value.get('seriesId') or (context or {}).get('series_id')
            current=dict(context or {})
            for k in ('series_id','race_id','race_name','track_name','event_name','date_scheduled','race_date','seriesId'):
                if k in value and value[k] not in (None,''):current[k]=value[k]
            schedule=value.get('schedule')
            if isinstance(schedule,list):
                for s in schedule:
                    if isinstance(s,dict):
                        item=dict(current);item.update(s);rows.append(item)
            elif value.get('start_time_utc') or value.get('startTimeUtc'):
                rows.append({**current,**value})
            for v in value.values():walk(v,current)
        elif isinstance(value,list):
            for v in value:walk(v,context)
    walk(root)
    return [r for r in rows if int(r.get('series_id') or r.get('seriesId') or 0)==series_id]

def add_nascar(events,report):
    """Use NASCAR's public CloudFront schedule cache; feed.nascar.com now returns 401 without partner auth."""
    year=NOW.year
    cache_urls={
        1:f'https://cf.nascar.com/cacher/{year}/1/race_list_basic.json',
        2:f'https://cf.nascar.com/cacher/{year}/race_list_basic.json',
        3:f'https://cf.nascar.com/cacher/{year}/race_list_basic.json',
    }
    loaded={}
    for series_id in (1,2,3):
        try:loaded[series_id]=get_json(cache_urls[series_id])
        except Exception as exc:report.setdefault('nascar',{})[next(n for n,s,_ in NASCAR if s==series_id)]=f'failed: {exc}'
    existing={(e.get('league'),e.get('title'),e.get('start')) for e in events}
    for league,series_id,icon in NASCAR:
        root=loaded.get(series_id)
        if root is None:continue
        rows=nascar_races(root,series_id);added=0
        for item in rows:
            dt=iso(item.get('start_time_utc') or item.get('startTimeUtc') or item.get('date_scheduled') or item.get('race_date'))
            if not dt:continue
            try:dt_obj=datetime.fromisoformat(dt.replace('Z','+00:00'))
            except ValueError:continue
            if not NOW-timedelta(hours=12) <= dt_obj <= HORIZON:continue
            event_name=str(item.get('event_name') or '').strip();race_name=str(item.get('race_name') or '').strip();track=str(item.get('track_name') or '').strip()
            run_type=int(item.get('run_type') or item.get('runType') or 0)
            kind={1:'Practice',2:'Qualifying',3:'Race'}.get(run_type,'Event')
            title=' — '.join(x for x in (race_name or event_name,kind if run_type else '',track if run_type else track) if x)
            if not title:title=league
            key=(league,title,dt)
            if key in existing:continue
            events.append({'league':league,'title':title,'start':dt,'tag':'LIVE' if run_type==3 and dt_obj<=NOW else 'UPCOMING','icon':icon,'source':'official_api','sourceDetail':'NASCAR CF schedule cache'})
            existing.add(key);added+=1
        report.setdefault('nascar',{})[league]=f'official_api:{added}'
        if added==0:print(f'WARNING NASCAR adapter returned zero normalized events for {league}')

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
        if key not in unique or str(e.get('source','')).startswith('official') or str(e.get('source','')).startswith('nascar'):
            unique[key]=e
    payload['events']=list(unique.values())
    counts={}
    for e in payload['events']:counts[e.get('league','')]=counts.get(e.get('league',''),0)+1
    payload['eventCounts']=counts;payload['officialApiAdapterReport']=report
    FEED.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('official API adapter report:',json.dumps(report,sort_keys=True));print(f'official API adapter total events: {len(payload["events"])}')
if __name__=='__main__':main()
