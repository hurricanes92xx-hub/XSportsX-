#!/usr/bin/env python3
"""Reconcile current live/final status from ESPN scoreboards."""
from __future__ import annotations
import json, re, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FEED=ROOT/'data'/'schedule_feed.json'
HEADERS={'User-Agent':'XSportsX-LiveStatus/1.5','Accept':'application/json'}
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
    with urllib.request.urlopen(urllib.request.Request(url,headers=HEADERS),timeout=12) as r:
        return json.loads(r.read().decode('utf-8','ignore'))

def dt(v):
    try: return datetime.fromisoformat(str(v).replace('Z','+00:00')).astimezone(timezone.utc)
    except Exception: return None

def iso(v):
    x=dt(v); return x.isoformat().replace('+00:00','Z') if x else None

def norm(v):
    return ' '.join(re.sub(r'[^a-z0-9]+',' ',re.sub(r'\b(at|vs\.?|versus)\b',' ',str(v or '').lower().replace('&',' and '))).split())

def league_key(v):
    # Treat apostrophe/punctuation variants as the same canonical league.
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

def find_match(events,league,name,start):
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

def main():
    payload=json.loads(FEED.read_text(encoding='utf-8')); events=payload.get('events') or []
    changed=added=failures=0; today=datetime.now(timezone.utc).date()
    for league,sport,slug in ESPN_LEAGUES:
        try: root=get_json(f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/scoreboard?dates={today:%Y%m%d}&limit=1000')
        except Exception as exc:
            failures+=1; print(f'LIVE RECONCILE: {league}: request failed: {exc}'); continue
        for remote in root.get('events') or []:
            start=iso(remote.get('date'))
            if not start: continue
            name=title(remote,league); tag=state(remote)
            if league=='MLB' and tag!='FINAL' and mlb_time_fallback(start,tag): tag='LIVE'
            event=find_match(events,league,name,start)
            if event is not None:
                if event.get('tag')!=tag:
                    event['tag']=tag; event['sourceDetail']='ESPN live-status reconciliation'; changed+=1
            elif tag=='LIVE':
                events.append({'league':league,'title':name,'start':start,'tag':'LIVE','icon':'•','source':'espn','sourceDetail':'ESPN live-status reconciliation'}); added+=1
    payload['events']=events
    payload['eventCounts']={k:sum(1 for e in events if e.get('league')==k) for k in sorted({e.get('league') for e in events if e.get('league')})}
    report=payload.setdefault('repairReport',{}); report['liveStatusReconciled']=changed; report['liveEventsAdded']=added; report['liveProviderFailures']=failures
    FEED.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f'LIVE RECONCILE: status_updates={changed}; live_events_added={added}; provider_failures={failures}')
    if failures: raise SystemExit(f'{failures} ESPN scoreboard providers failed')

if __name__=='__main__': main()
