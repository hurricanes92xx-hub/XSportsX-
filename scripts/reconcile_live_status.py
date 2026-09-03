#!/usr/bin/env python3
"""Reconcile current live/final status from authoritative scoreboards.

This is a live-state pass, not a schedule rebuild. Provider failures are
isolated and recorded so a healthy schedule is not discarded because one
scoreboard is temporarily unavailable.
"""
from __future__ import annotations
import json, re, time, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from event_identity import event_identity, provider_identity

ROOT=Path(__file__).resolve().parents[1]
FEED=ROOT/'data'/'schedule_feed.json'
HEADERS={'User-Agent':'XSportsX-LiveStatus/2.0','Accept':'application/json'}
ESPN_LEAGUES=[
    ('NFL','football','nfl'),('NCAA FB','football','college-football'),('CFL','football','cfl'),
    ('NBA','basketball','nba'),('WNBA','basketball','wnba'),('NCAA BB','basketball','mens-college-basketball'),('NCAA WBB','basketball','womens-college-basketball'),
    ('MLB','baseball','mlb'),('NCAA BASEBALL','baseball','college-baseball'),('NHL','hockey','nhl'),
    ('NCAA MEN HOCKEY','hockey','mens-college-hockey'),('NCAA WOMEN HOCKEY','hockey','womens-college-hockey'),('NCAA SOFTBALL','softball','college-softball'),
    ('MLS','soccer','usa.1'),('NWSL','soccer','usa.nwsl'),('NCAA Men Soccer','soccer','usa.ncaa.m.1'),('NCAA Women Soccer','soccer','usa.ncaa.w.1'),
    ('EPL','soccer','eng.1'),('UCL','soccer','uefa.champions'),('UEL','soccer','uefa.europa'),('LaLiga','soccer','esp.1'),('Serie A','soccer','ita.1'),('Bundesliga','soccer','ger.1'),('Ligue 1','soccer','fra.1'),
    ('UFC','mma','ufc'),('F1','racing','f1'),('IndyCar','racing','irl'),('NASCAR Cup','racing','nascar-premier'),('PGA','golf','pga'),('LPGA','golf','lpga'),('LIV Golf','golf','liv'),
    ('ATP','tennis','atp'),('WTA','tennis','wta'),('PLL','lacrosse','pll'),('NLL','lacrosse','nll'),('NCAA MEN LAX','lacrosse','mens-college-lacrosse'),('NCAA WOMEN LAX','lacrosse','womens-college-lacrosse'),
    ('FIVB Men','volleyball','fivb.m'),('FIVB Women','volleyball','fivb.w'),('NCAA VB','volleyball','womens-college-volleyball'),('NRL','rugby-league','3'),('AFL','australian-football','afl'),('ICC T20','cricket','icc.t20'),('IPL','cricket','ipl')
]

def get_json(url):
    last=None
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers=HEADERS)
            with urllib.request.urlopen(req,timeout=12) as r:
                return json.loads(r.read().decode('utf-8','ignore'))
        except Exception as exc:
            last=exc
            if attempt < 2: time.sleep(0.75*(attempt+1))
    raise last

def dt(v):
    try: return datetime.fromisoformat(str(v).replace('Z','+00:00')).astimezone(timezone.utc)
    except Exception: return None

def iso(v):
    x=dt(v); return x.isoformat().replace('+00:00','Z') if x else None

def norm(v):
    return ' '.join(re.sub(r'[^a-z0-9]+',' ',re.sub(r'\b(at|vs\.?|versus)\b',' ',str(v or '').lower().replace('&',' and '))).split())

def league_key(v):
    return norm(v).replace(' men s ',' men ').replace(' women s ',' women ')

def parts(v): return {x for x in norm(v).split() if len(x)>=3}

def title(event,league):
    c=(event.get('competitions') or [{}])[0]; t=c.get('competitors') or []
    h=next((x.get('team',{}).get('shortDisplayName') or x.get('team',{}).get('displayName') for x in t if x.get('homeAway')=='home'),'')
    a=next((x.get('team',{}).get('shortDisplayName') or x.get('team',{}).get('displayName') for x in t if x.get('homeAway')=='away'),'')
    return f'{a} @ {h}' if a and h else str(event.get('name') or event.get('shortName') or league)

def state(event):
    c=(event.get('competitions') or [{}])[0]; s=((c.get('status') or {}).get('type') or {}) or ((event.get('status') or {}).get('type') or {})
    return {'in':'LIVE','post':'FINAL','final':'FINAL'}.get(str(s.get('state') or 'pre').lower(),'UPCOMING')

def mlb_time_fallback(start,tag):
    if tag=='FINAL': return False
    remote=dt(start)
    if not remote: return False
    now=datetime.now(timezone.utc)
    return remote+timedelta(minutes=20)<=now<=remote+timedelta(hours=5)

def find_match(events,league,name,start,provider_id='',provider=''):
    wanted_provider=provider_identity(provider,provider_id)
    if wanted_provider:
        exact_provider=[e for e in events if e.get('providerEventId')==wanted_provider]
        if len(exact_provider)==1: return exact_provider[0]
    logical_id=event_identity(league,name,start)
    exact_id=[e for e in events if e.get('eventId')==logical_id]
    if len(exact_id)==1: return exact_id[0]
    remote=dt(start); tokens=parts(name); wanted=league_key(league)
    candidates=[e for e in events if league_key(e.get('league'))==wanted]
    exact=[e for e in candidates if iso(e.get('start'))==start]
    if exact: candidates=exact
    else:
        near=[]
        for e in candidates:
            old=dt(e.get('start'))
            if remote and old and abs((old-remote).total_seconds())<=10800:
                shared=len(tokens & parts(e.get('title')))
                if shared: near.append((shared,-abs((old-remote).total_seconds()),e))
        if near: return sorted(near,key=lambda x:(x[0],x[1]),reverse=True)[0][2]
        return None
    if len(candidates)==1: return candidates[0]
    ranked=sorted(((len(tokens & parts(e.get('title'))),e) for e in candidates),key=lambda x:x[0],reverse=True)
    return ranked[0][1] if ranked and ranked[0][0] else None

def annotate(event,provider='',provider_id=''):
    event['eventId']=event_identity(event.get('league'),event.get('title'),event.get('start'))
    pid=provider_identity(provider,provider_id)
    if pid: event['providerEventId']=pid

def reconcile_mlb_authoritative(events,today):
    changed=added=0
    for game_date in (today-timedelta(days=1), today):
        root=get_json(f'https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={game_date:%Y-%m-%d}&hydrate=team,linescore')
        for date_block in root.get('dates') or []:
            for game in date_block.get('games') or []:
                status=game.get('status') or {}; abstract=str(status.get('abstractGameState') or '').lower(); detailed=str(status.get('detailedState') or '').lower()
                if abstract not in {'live','in progress'} and 'progress' not in detailed and detailed not in {'live'}: continue
                teams=(game.get('teams') or {}); away=((teams.get('away') or {}).get('team') or {}).get('name') or ''; home=((teams.get('home') or {}).get('team') or {}).get('name') or ''
                start=iso(game.get('gameDate'))
                if not away or not home or not start: continue
                name=f'{away} @ {home}'; provider_id=str(game.get('gamePk') or '')
                event=find_match(events,'MLB',name,start,provider_id,'mlb')
                if event is None:
                    event={'league':'MLB','title':name,'start':start,'tag':'LIVE','icon':'•','source':'mlb','sourceDetail':'MLB Stats API live-status reconciliation'}; annotate(event,'mlb',provider_id); events.append(event); added+=1
                else:
                    old=event.get('tag'); event['tag']='LIVE'; event['sourceDetail']='MLB Stats API live-status reconciliation'; annotate(event,'mlb',provider_id); changed += old!='LIVE'
    return changed,added

def main():
    payload=json.loads(FEED.read_text(encoding='utf-8')); events=payload.get('events') or []
    for event in events: annotate(event,event.get('source',''),event.get('providerEventId','').split(':',1)[-1] if ':' in str(event.get('providerEventId','')) else '')
    changed=added=failures=0; today=datetime.now(timezone.utc).date(); failed_providers=[]
    for league,sport,slug in ESPN_LEAGUES:
        dates=(today-timedelta(days=1),today) if league=='MLB' else (today,)
        for scoreboard_date in dates:
            try: root=get_json(f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/scoreboard?dates={scoreboard_date:%Y%m%d}&limit=1000')
            except Exception as exc:
                failures+=1; failed_providers.append(f'{league}:{scoreboard_date}'); print(f'LIVE RECONCILE: {league} {scoreboard_date}: unavailable after retries: {exc}'); continue
            for remote in root.get('events') or []:
                start=iso(remote.get('date'))
                if not start: continue
                name=title(remote,league); tag=state(remote); remote_id=str(remote.get('id') or '')
                if league=='MLB' and tag!='FINAL' and mlb_time_fallback(start,tag): tag='LIVE'
                event=find_match(events,league,name,start,remote_id,'espn')
                if event is not None:
                    annotate(event,'espn',remote_id)
                    if event.get('tag')!=tag: event['tag']=tag; event['sourceDetail']='ESPN live-status reconciliation'; changed+=1
                elif tag=='LIVE':
                    event={'league':league,'title':name,'start':start,'tag':'LIVE','icon':'•','source':'espn','sourceDetail':'ESPN live-status reconciliation'}; annotate(event,'espn',remote_id); events.append(event); added+=1
    try:
        c,a=reconcile_mlb_authoritative(events,today); changed+=c; added+=a
        print(f'LIVE RECONCILE: MLB authoritative status_updates={c}; live_events_added={a}')
    except Exception as exc:
        failures+=1; failed_providers.append('MLB Stats API'); print(f'LIVE RECONCILE: MLB Stats API unavailable after retries: {exc}')
    payload['events']=events
    payload['eventCounts']={k:sum(1 for e in events if e.get('league')==k) for k in sorted({e.get('league') for e in events if e.get('league')})}
    report=payload.setdefault('repairReport',{}); report['liveStatusReconciled']=changed; report['liveEventsAdded']=added; report['liveProviderFailures']=failures; report['liveFailedProviders']=failed_providers
    FEED.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f'LIVE RECONCILE: status_updates={changed}; live_events_added={added}; provider_failures={failures}; identity_annotated={len(events)}')
    # Live reconciliation is intentionally best-effort. The canonical schedule
    # validator decides whether the resulting feed is publishable.

if __name__=='__main__': main()
