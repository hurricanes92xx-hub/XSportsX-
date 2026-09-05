#!/usr/bin/env python3
"""Supplemental adapters for sports whose primary feeds are unreliable.

Rules: never invent LIVE. OpenF1 is used for F1 session truth, NASCAR gets
official LiveFeed first with ESPN fallback, cricket uses keyed cricket APIs,
and X Games is treated as an official schedule/event source rather than a
scoreboard API. FIVB is deliberately handled only by official_live_adapters.
"""
from __future__ import annotations
import json, os, re, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]; FEED=ROOT/'data/schedule_feed.json'
UA='XSportsX-SupplementalAdapters/1.0'

def get(url,headers=None,timeout=10):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json,text/plain,*/*',**(headers or {})})
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode('utf-8','ignore'))

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

def f1():
    now=datetime.now(timezone.utc); out=[]; diag={'status':'ok','sessions':0,'live':0,'upcoming':0,'errors':[]}
    y=now.year
    try: meetings=get(f'https://api.openf1.org/v1/meetings?year={y}')
    except Exception as e:return out,{**diag,'status':'unavailable','errors':[type(e).__name__]}
    for m in meetings if isinstance(meetings,list) else []:
        mk=m.get('meeting_key')
        if not mk:continue
        try:sessions=get(f'https://api.openf1.org/v1/sessions?meeting_key={mk}')
        except Exception as e:diag['errors'].append(type(e).__name__);continue
        for s in sessions if isinstance(sessions,list) else []:
            st=iso(s.get('date_start')); en=iso(s.get('date_end'))
            if not st:continue
            a=datetime.fromisoformat(st.replace('Z','+00:00')); b=datetime.fromisoformat(en.replace('Z','+00:00')) if en else a+timedelta(hours=2)
            if a<=now<=b+timedelta(minutes=2):
                out.append(row('F1',f"{m.get('meeting_name') or m.get('country_name') or 'Formula 1'} — {s.get('session_name') or 'Session'}",st,'openf1',f"openf1:{s.get('session_key')}",True));diag['live']+=1
            elif b>=now-timedelta(hours=2) and a<=now+timedelta(days=8):
                out.append(row('F1',f"{m.get('meeting_name') or m.get('country_name') or 'Formula 1'} — {s.get('session_name') or 'Session'}",st,'openf1',f"openf1:{s.get('session_key')}",False));diag['upcoming']+=1
            diag['sessions']+=1
    return out,diag

def nascar():
    now=datetime.now(timezone.utc); out=[]; diag={'status':'ok','official':False,'espn':False,'live':0,'errors':[]}
    for v in ('1','2'):
        try:
            x=get(f'https://feed.nascar.com/api/LiveFeed?v={v}',{'Referer':'https://www.nascar.com/','Origin':'https://www.nascar.com'})
            diag['official']=True
            for z in x if isinstance(x,list) else [x]:
                if not isinstance(z,dict) or str(z.get('series_id') or z.get('seriesId'))!='3':continue
                nm=z.get('run_name') or z.get('event_name') or 'NASCAR Craftsman Truck Series'; rid=z.get('race_id') or z.get('raceId') or z.get('run_id')
                out.append(row('NASCAR Truck',nm,iso(z.get('time_of_day_os')),'nascar-livefeed-official',f'nascar:live:{rid}',True));diag['live']+=1
            if out:return out,diag
        except Exception as e:diag['errors'].append(f'official:{type(e).__name__}')
    # ESPN is a recovery source when NASCAR blocks cloud runners. Query a 3-day UTC window.
    for d in (-1,0,1):
        dt=now+timedelta(days=d); ds=dt.strftime('%Y%m%d')
        for slug in ('nascar-truck','nascar-craftsman-truck-series'):
            try:
                x=get(f'https://site.api.espn.com/apis/site/v2/sports/racing/{slug}/scoreboard?dates={ds}')
                diag['espn']=True
                for ev in x.get('events') or []:
                    comp=' '.join(str(ev.get('name') or '') for _ in [0])
                    start=iso(ev.get('date')); status=(((ev.get('competitions') or [{}])[0]).get('status') or {}).get('type') or {}
                    st=str(status.get('state') or '').lower();live=st in {'in','in_progress'}
                    if not start or ('truck' not in norm(comp) and 'craftsman' not in norm(comp)):continue
                    out.append(row('NASCAR Truck',comp,start,'espn-nascar-shadow',f"espn:{ev.get('id')}",live))
                    if live:diag['live']+=1
                if out:return out,diag
            except Exception as e:diag['errors'].append(f'espn:{type(e).__name__}')
    if not diag['official'] and not diag['espn']:diag['status']='unavailable'
    return out,diag

def cricket():
    out=[];diag={'status':'not-configured','cricketdata':False,'criclive':False,'live':0,'errors':[]}
    key=os.getenv('CRICKETDATA_API_KEY','').strip()
    if key:
        try:
            x=get(f'https://api.cricketdata.org/v1/currentMatches?apikey={urllib.parse.quote(key)}&offset=0');diag['cricketdata']=True;diag['status']='ok'
            for z in x.get('data') or []:
                n=str(z.get('name') or z.get('matchType') or ''); nn=norm(n)
                league='IPL' if 'ipl' in nn else 'ICC T20' if 't20' in nn or 'icc' in nn else ''
                ti=z.get('teamInfo') or []; home=name(ti[0] if ti else z.get('homeTeam'));away=name(ti[1] if len(ti)>1 else z.get('awayTeam'))
                started=str(z.get('matchStarted')).lower()=='true';ended=str(z.get('matchEnded')).lower()=='true';live=started and not ended
                if league and home and away:out.append(row(league,f'{away} @ {home}',iso(z.get('dateTimeGMT') or z.get('dateTime')),'cricketdata',f"cricketdata:{z.get('id') or nn}",live,home,away));diag['live']+=int(live)
        except Exception as e:diag['errors'].append(f'cricketdata:{type(e).__name__}')
    key=os.getenv('CRICLIVE_API_KEY','').strip()
    if key:
        try:
            x=get(f'https://api.cricketliveapi.com/api/v1/matches/live?api_key={urllib.parse.quote(key)}');diag['criclive']=True;diag['status']='ok'
            for z in x.get('data') or x.get('matches') or []:
                comp=str(z.get('series') or z.get('competition') or '');nn=norm(comp);league='IPL' if 'ipl' in nn else 'ICC T20' if 't20' in nn or 'icc' in nn else ''
                home=name(z.get('home_team') or z.get('homeTeam'));away=name(z.get('away_team') or z.get('awayTeam'))
                if league and home and away:out.append(row(league,f'{away} @ {home}',iso(z.get('start_time') or z.get('startTime') or z.get('date')),'criclive',f"criclive:{z.get('id') or norm(home+'-'+away)}",True,home,away));diag['live']+=1
        except Exception as e:diag['errors'].append(f'criclive:{type(e).__name__}')
    return out,diag

def xgames():
    # Official X Games pages are an event/schedule source; there is no verified public live-score API.
    # Keep diagnostics explicit and do not manufacture LIVE.
    return [],{'status':'schedule-only','live':0,'source':'xgames-official','note':'Official X Games schedule/results are used by event recovery; no public live scoreboard endpoint is assumed.'}

def main():
    if not FEED.exists():raise SystemExit('missing schedule feed')
    p=json.loads(FEED.read_text());events=[e for e in p.get('events') or [] if isinstance(e,dict)]
    checked=str((p.get('liveSweep') or {}).get('checkedAtUtc') or datetime.now(timezone.utc).isoformat().replace('+00:00','Z'))
    allrows=[];diagnostics={}
    for n,fn in (('F1',f1),('NASCAR Truck',nascar),('Cricket',cricket),('X Games',xgames)):
        try:r,d=fn();allrows.extend(r);diagnostics[n]=d
        except Exception as e:diagnostics[n]={'status':'error','errors':[type(e).__name__]}
    added=live=0
    def ident(e):return (norm(e.get('league')),norm(e.get('away')),norm(e.get('home')),norm(e.get('title')))
    for r in allrows:
        match=next((e for e in events if (norm(e.get('league'))==norm(r.get('league')) and (norm(e.get('away'))==norm(r.get('away')) or norm(e.get('title'))==norm(r.get('title'))))),None)
        if match:
            if r['tag']=='LIVE':
                match.update({'tag':'LIVE','status':'LIVE','state':'in','liveStateSource':'supplemental-adapter','liveEvidence':{'providerEventId':r['providerEventId'],'provider':r['source'],'checkedAtUtc':checked}});live+=1
            elif not match.get('startUtc') and r.get('startUtc'):match.update({'startUtc':r['startUtc'],'start':r['start']})
        elif r['tag']!='LIVE':
            events.append(r);added+=1
        else:
            r['liveEvidence']={'providerEventId':r['providerEventId'],'provider':r['source'],'checkedAtUtc':checked};r['liveStateSource']='supplemental-adapter';events.append(r);added+=1;live+=1
    p['events']=events;p['supplementalLiveAdapters']={'checkedAtUtc':checked,'diagnostics':diagnostics,'eventsAdded':added,'liveApplied':live}
    FEED.write_text(json.dumps(p,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(p['supplementalLiveAdapters'],indent=2))

if __name__=='__main__':main()
