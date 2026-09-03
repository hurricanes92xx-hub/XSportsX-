#!/usr/bin/env python3
# Canonical schedule publisher: official sources first, provider authorities second.
# NCAA and NASCAR now have dedicated providers instead of daily endpoint loops.
import json
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

from providers.sportsdb import fetch_league, current_season, SPORTDB_LEAGUES
from providers.ncaa import fetch_league as fetch_ncaa_league, NCAA_LEAGUES
from providers.nascar import fetch_league as fetch_nascar_league, SERIES as NASCAR_SERIES

OUT = Path('data/schedule_feed.json')
OFFICIAL_REGISTRY = Path('data/official_schedule_sources.json')
HEADERS = {
    'User-Agent': 'XSportsX-Schedule/3.0',
    'Accept': 'application/json, text/plain, text/html, */*',
    'Accept-Language': 'en-US,en;q=0.9',
}

ESPN_LEAGUES = [
    ('NFL','football','nfl','🏈',14), ('CFL','football','cfl','🏈',30),
    ('NBA','basketball','nba','🏀',30), ('WNBA','basketball','wnba','🏀',30),
    ('NHL','hockey','nhl','🏒',30), ('NCAA Women\'s Hockey','hockey','womens-college-hockey','🏒',180),
    ('MLB','baseball','mlb','⚾',30),
    ('MLS','soccer','usa.1','⚽',30), ('EPL','soccer','eng.1','⚽',30), ('UCL','soccer','uefa.champions','⚽',30),
    ('LaLiga','soccer','esp.1','⚽',30), ('Serie A','soccer','ita.1','⚽',30), ('Bundesliga','soccer','ger.1','⚽',30), ('Ligue 1','soccer','fra.1','⚽',30),
    ('UFC','mma','ufc','🥊',30),
    ('F1','racing','f1','🏎️',30), ('IndyCar','racing','irl','🏎️',30),
    ('PGA','golf','pga','⛳',30), ('LPGA','golf','lpga','⛳',30), ('LIV Golf','golf','liv','⛳',30),
    ('ATP','tennis','atp','🎾',30), ('WTA','tennis','wta','🎾',30),
    ('PLL','lacrosse','pll','🥍',30), ('NLL','lacrosse','nll','🥍',30),
    ('FIVB Men','volleyball','fivb.m','🏐',30), ('FIVB Women','volleyball','fivb.w','🏐',30),
    ('Rugby World Cup','rugby','164205','🏉',30), ('Six Nations','rugby','180659','🏉',30),
    ('NRL','rugby-league','3','🏉',30), ('AFL','australian-football','afl','🏉',30),
    ('ICC T20','cricket','icc.t20','🏏',30), ('IPL','cricket','ipl','🏏',30),
]

WRESTLING_FALLBACK = [
    ('WWE','Monday Night Raw','2026-09-07T00:00:00Z','SPECIAL','🏆'), ('WWE','Monday Night Raw','2026-09-14T00:00:00Z','SPECIAL','🏆'),
    ('WWE','Monday Night Raw','2026-09-21T00:00:00Z','SPECIAL','🏆'), ('WWE','Monday Night Raw','2026-09-28T00:00:00Z','SPECIAL','🏆'),
    ('WWE','Monday Night Raw','2026-10-05T00:00:00Z','SPECIAL','🏆'), ('WWE','Monday Night Raw','2026-10-12T00:00:00Z','SPECIAL','🏆'),
    ('WWE','Monday Night Raw','2026-10-19T00:00:00Z','SPECIAL','🏆'), ('WWE','Monday Night Raw','2026-10-26T00:00:00Z','SPECIAL','🏆'),
    ('WWE','Monday Night Raw','2026-11-02T00:00:00Z','SPECIAL','🏆'), ('WWE','NXT Heatwave','2026-08-30T17:00:00Z','SPECIAL','🏆'),
    ('WWE',"Sunday Night's Main Event",'2026-09-07T00:00:00Z','SPECIAL','🏆'), ('WWE','Worlds Collide','2026-09-27T00:00:00Z','PLE','🏆'),
    ('WWE','Money in the Bank','2026-10-10T22:00:00Z','PLE','🏆'), ('WWE','Survivor Series: WarGames','2026-11-29T00:00:00Z','PLE','🏆'),
    ('AEW','All In: London','2026-08-30T15:30:00Z','PPV','🤼'), ('AEW','All Out','2026-09-26T23:00:00Z','PPV','🤼'),
    ('AEW','Grand Slam: France','2026-10-06T00:00:00Z','SPECIAL','🤼'), ('AEW','WrestleDream','2026-10-17T23:00:00Z','PPV','🤼'),
    ('AEW','Full Gear','2026-11-14T23:00:00Z','PPV','🤼'), ('TNA','Bound for Glory','2026-10-11T20:00:00Z','PPV','🤼'),
]
OFFICIAL_WRESTLING = [('WWE','https://www.wwe.com/article/wwe-upcoming-events','🏆'),('AEW','https://www.allelitewrestling.com/aew-events','🤼'),('TNA','https://tnawrestling.com/events/','🤼')]


def get(url):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=12) as r: return r.read()


def load_official_registry():
    try:
        root=json.loads(OFFICIAL_REGISTRY.read_text(encoding='utf-8'))
        return root.get('officialSources') or []
    except Exception as exc:
        print(f'ERROR official registry: {exc}')
        return []


def parse_iso(value):
    if not value: return None
    try:
        return datetime.fromisoformat(str(value).replace('Z','+00:00')).astimezone(timezone.utc)
    except Exception:
        return None


def jsonld_objects(html):
    for m in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',html,re.I|re.S):
        try:
            v=json.loads(m.strip())
            vals=[]
            if isinstance(v,list): vals=v
            elif isinstance(v,dict):
                if v.get('@type'): vals.append(v)
                if isinstance(v.get('@graph'),list): vals.extend(v['@graph'])
            for o in vals:
                if isinstance(o,dict): yield o
        except Exception:
            continue


def add_official_source(events, source):
    name=str(source.get('league') or '').strip(); url=str(source.get('url') or '').strip()
    if not name or not url: return False,0
    try: html=get(url).decode('utf-8','ignore')
    except Exception as exc:
        print(f'ERROR official {name}: {exc}')
        return False,0
    added=0; now=datetime.now(timezone.utc)-timedelta(hours=12); horizon=datetime.now(timezone.utc)+timedelta(days=370)
    for obj in jsonld_objects(html):
        kind=obj.get('@type'); is_event=kind=='Event' or (isinstance(kind,list) and 'Event' in kind)
        if not is_event: continue
        title=str(obj.get('name') or '').strip(); dt=parse_iso(obj.get('startDate'))
        if not title or not dt or dt < now or dt > horizon: continue
        events.append({'league':name,'title':title,'start':dt.isoformat().replace('+00:00','Z'),'tag':'UPCOMING','icon':'🏆','source':'official'}); added+=1
    return True,added


def add_official_sources(events):
    failures=[]; counts={}
    for source in load_official_registry():
        ok,n=add_official_source(events,source); name=source.get('league','')
        counts[name]=n
        if not ok: failures.append(name)
    return failures,counts


def get_espn(url):
    last=None
    for target in (url.replace('https://site.api.espn.com','https://site.web.api.espn.com'),url):
        try: return get(target)
        except Exception as exc: last=exc; print(f'ERROR ESPN request {target}: {exc}')
    raise last


def add_espn(events,name,sport,league,icon,days):
    start=datetime.now(timezone.utc).date(); end=start+timedelta(days=days)
    url=f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={start:%Y%m%d}-{end:%Y%m%d}&limit=1000'
    try: root=json.loads(get_espn(url))
    except Exception as exc: print(f'ERROR ESPN {name}: {exc}'); return False,0
    raw=root.get('events')
    if not isinstance(raw,list): return False,0
    added=0
    for event in raw:
        comp=(event.get('competitions') or [{}])[0]; teams=comp.get('competitors') or []
        home=next((x.get('team',{}).get('shortDisplayName') or x.get('team',{}).get('displayName') for x in teams if x.get('homeAway')=='home'),'')
        away=next((x.get('team',{}).get('shortDisplayName') or x.get('team',{}).get('displayName') for x in teams if x.get('homeAway')=='away'),'')
        title=f'{away} @ {home}' if home and away else (event.get('name') or event.get('shortName') or name)
        status=((comp.get('status') or {}).get('type') or {}); state=status.get('state','pre')
        tag='LIVE' if state=='in' else ('FINAL' if state=='post' else 'UPCOMING')
        if event.get('date'):
            events.append({'league':name,'title':title,'start':event['date'],'tag':tag,'icon':icon,'source':'espn'}); added+=1
    return True,added


def add_sportsdb(events,name,icon):
    if name not in SPORTDB_LEAGUES:
        return False,0
    raw=fetch_league(name,current_season())
    if not raw:
        return False,0
    for event in raw:
        event['icon']=icon
        events.append(event)
    return True,len(raw)


def add_wrestling(events):
    found_events=set()
    for brand,url,icon in OFFICIAL_WRESTLING:
        try: html=get(url).decode('utf-8','ignore')
        except Exception: continue
        for o in jsonld_objects(html):
            kind=o.get('@type'); title=str(o.get('name') or '').strip(); start=str(o.get('startDate') or '').strip()
            if (kind=='Event' or (isinstance(kind,list) and 'Event' in kind)) and title and start:
                dt=parse_iso(start)
                if dt and dt>=datetime.now(timezone.utc)-timedelta(hours=6):
                    events.append({'league':brand,'title':title,'start':dt.isoformat().replace('+00:00','Z'),'tag':'SPECIAL','icon':icon,'source':'official'}); found_events.add((brand,title,dt.strftime('%Y-%m-%d')))
    for brand,title,start,tag,icon in WRESTLING_FALLBACK:
        dt=parse_iso(start); key=(brand,title,dt.strftime('%Y-%m-%d')) if dt else None
        if dt and key not in found_events and dt>=datetime.now(timezone.utc)-timedelta(hours=6):
            events.append({'league':brand,'title':title,'start':start,'tag':tag,'icon':icon,'source':'fallback'})


def main():
    events=[]; failures=[]; counts={}; sportsdb_failures=[]; provider_failures=[]
    official_failures,official_counts=add_official_sources(events)
    add_wrestling(events)

    # ESPN remains the general provider. NCAA and NASCAR are intentionally
    # removed from this list so their dedicated authorities own those lanes.
    for league in ESPN_LEAGUES:
        ok,n=add_espn(events,*league); counts[league[0]]=n
        if not ok:
            failures.append(league[0])
            db_ok,db_n=add_sportsdb(events,league[0],league[3])
            if db_ok:
                counts[league[0]]=db_n; sportsdb_failures.append(league[0])

    # NCAA primary: month-based schedule endpoints, not one request per day.
    for name,sport,division,icon in NCAA_LEAGUES:
        raw=fetch_ncaa_league(name,sport,division,icon,horizon_days=30)
        counts[name]=len(raw)
        if raw:
            events.extend(raw)
        else:
            provider_failures.append(name)
            failures.append(name)

    # NASCAR primary: official feed.nascar.com season schedule.
    for name in NASCAR_SERIES:
        raw=fetch_nascar_league(name,horizon_days=370)
        counts[name]=len(raw)
        if raw:
            events.extend(raw)
        else:
            provider_failures.append(name)
            # ESPN is the structured secondary authority for NASCAR only when
            # the official NASCAR feed is unavailable.
            espn_ok,espn_n=add_espn(events,name,'racing','nascar-premier','🏎️',30)
            if espn_ok:
                counts[name]=espn_n
            else:
                failures.append(name)

    previous={}
    if OUT.exists():
        try: previous=json.loads(OUT.read_text(encoding='utf-8'))
        except Exception: previous={}
    prev_events=previous.get('events') or []
    present_leagues={e.get('league') for e in events}
    for league in failures:
        if league in present_leagues: continue
        events.extend(e for e in prev_events if e.get('league')==league)
        counts[league]=sum(1 for e in events if e.get('league')==league)

    priority={'official':0,'ncaa':1,'nascar':1,'espn':2,'sportsdb':3,'fallback':4,None:5}
    unique={}
    for event in events:
        event=event.copy(); source=event.pop('source',None); event['_sourcePriority']=priority.get(source,5)
        key=(event.get('league'),event.get('title'),event.get('start'))
        old=unique.get(key)
        if old is None or event['_sourcePriority'] < old['_sourcePriority']:
            unique[key]=event
    events=[]
    for event in unique.values():
        event.pop('_sourcePriority',None); events.append(event)
    events=sorted(events,key=lambda e:e.get('start',''))
    per={}
    for e in events: per[e['league']]=per.get(e['league'],0)+1

    payload={
        'schema':6,
        'generatedAt':datetime.now(timezone.utc).isoformat(),
        'refreshHours':6,
        'eventCounts':per,
        'failedSources':failures,
        'providerFailures':provider_failures,
        'sportsDbFallbackSources':sportsdb_failures,
        'officialSourceFailures':official_failures,
        'officialSourceCounts':official_counts,
        'events':events,
    }
    tmp=OUT.with_suffix('.tmp'); tmp.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); tmp.replace(OUT)
    print(f'wrote {len(events)} events across {len(per)} leagues; provider_failures={provider_failures}; sportsdb_fallbacks={sportsdb_failures}; official_failures={official_failures}')


if __name__=='__main__':main()
