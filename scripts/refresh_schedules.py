#!/usr/bin/env python3
# Canonical schedule publisher: official sources first, provider fallbacks second.
# Official events are preferred when the same event is found by multiple sources;
# fallbacks remain enabled so an official page that exposes only partial structured
# data cannot make an otherwise healthy league disappear.
import json, re, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

OUT = Path('data/schedule_feed.json')
OFFICIAL_REGISTRY = Path('data/official_schedule_sources.json')
HEADERS = {
    'User-Agent': 'XSportsX-Schedule/2.0',
    'Accept': 'application/json, text/plain, text/html, */*',
    'Accept-Language': 'en-US,en;q=0.9',
}

ESPN_LEAGUES = [
    ('NFL','football','nfl','🏈',14), ('NCAA FB','football','college-football','🏈',60), ('CFL','football','cfl','🏈',30),
    ('NBA','basketball','nba','🏀',30), ('WNBA','basketball','wnba','🏀',30),
    ('NHL','hockey','nhl','🏒',30), ('NCAA Women\'s Hockey','hockey','womens-college-hockey','🏒',180),
    ('MLB','baseball','mlb','⚾',30),
    ('MLS','soccer','usa.1','⚽',30), ('EPL','soccer','eng.1','⚽',30), ('UCL','soccer','uefa.champions','⚽',30),
    ('LaLiga','soccer','esp.1','⚽',30), ('Serie A','soccer','ita.1','⚽',30), ('Bundesliga','soccer','ger.1','⚽',30), ('Ligue 1','soccer','fra.1','⚽',30),
    ('UFC','mma','ufc','🥊',30),
    ('F1','racing','f1','🏎️',30), ('IndyCar','racing','irl','🏎️',30), ('NASCAR Cup','racing','nascar-premier','🏎️',30),
    ('PGA','golf','pga','⛳',30), ('LPGA','golf','lpga','⛳',30), ('LIV Golf','golf','liv','⛳',30),
    ('ATP','tennis','atp','🎾',30), ('WTA','tennis','wta','🎾',30),
    ('PLL','lacrosse','pll','🥍',30), ('NLL','lacrosse','nll','🥍',30),
    ('FIVB Men','volleyball','fivb.m','🏐',30), ('FIVB Women','volleyball','fivb.w','🏐',30),
    ('Rugby World Cup','rugby','164205','🏉',30), ('Six Nations','rugby','180659','🏉',30),
    ('NRL','rugby-league','3','🏉',30), ('AFL','australian-football','afl','🏉',30),
    ('ICC T20','cricket','icc.t20','🏏',30), ('IPL','cricket','ipl','🏏',30),
]
NCAA_LEAGUES = [
    ('NCAA BB','basketball-men','d1','🏀'), ('NCAA WBB','basketball-women','d1','🏀'),
    ('NCAA Baseball','baseball','d1','⚾'), ('NCAA Softball','softball','d1','🥎'),
    ('NCAA Men\'s Hockey','icehockey-men','d1','🏒'), ('NCAA Men\'s Soccer','soccer-men','d1','⚽'),
    ('NCAA Women\'s Soccer','soccer-women','d1','⚽'), ('NCAA Men\'s Lacrosse','lacrosse-men','d1','🥍'),
    ('NCAA Women\'s Lacrosse','lacrosse-women','d1','🥍'), ('NCAA Men\'s Volleyball','volleyball-men','d1','🏐'),
    ('NCAA Women\'s Volleyball','volleyball-women','d1','🏐'), ('NCAA Men\'s Water Polo','waterpolo-men','d1','🤽'),
    ('NCAA Women\'s Water Polo','waterpolo-women','d1','🤽'), ('NCAA Women\'s Field Hockey','fieldhockey-women','d1','🏑'),
    ('NCAA Beach Volleyball','beach-volleyball','d1','🏐'),
]
WRESTLING_FALLBACK = [
    ('WWE','Monday Night Raw','2026-08-31T00:00:00Z','SPECIAL','🏆'), ('WWE','Monday Night Raw','2026-09-07T00:00:00Z','SPECIAL','🏆'),
    ('WWE','Monday Night Raw','2026-09-14T00:00:00Z','SPECIAL','🏆'), ('WWE','Monday Night Raw','2026-09-21T00:00:00Z','SPECIAL','🏆'),
    ('WWE','Monday Night Raw','2026-09-28T00:00:00Z','SPECIAL','🏆'), ('WWE','Monday Night Raw','2026-10-05T00:00:00Z','SPECIAL','🏆'),
    ('WWE','Monday Night Raw','2026-10-12T00:00:00Z','SPECIAL','🏆'), ('WWE','Monday Night Raw','2026-10-19T00:00:00Z','SPECIAL','🏆'),
    ('WWE','Monday Night Raw','2026-10-26T00:00:00Z','SPECIAL','🏆'), ('WWE','Monday Night Raw','2026-11-02T00:00:00Z','SPECIAL','🏆'),
    ('WWE','NXT Heatwave','2026-08-30T17:00:00Z','SPECIAL','🏆'), ('WWE',"Sunday Night's Main Event",'2026-09-07T00:00:00Z','SPECIAL','🏆'),
    ('WWE','Worlds Collide','2026-09-27T00:00:00Z','PLE','🏆'), ('WWE','Money in the Bank','2026-10-10T22:00:00Z','PLE','🏆'),
    ('WWE','Survivor Series: WarGames','2026-11-29T00:00:00Z','PLE','🏆'), ('AEW','All In: London','2026-08-30T15:30:00Z','PPV','🤼'),
    ('AEW','All Out','2026-09-26T23:00:00Z','PPV','🤼'), ('AEW','Grand Slam: France','2026-10-06T00:00:00Z','SPECIAL','🤼'),
    ('AEW','WrestleDream','2026-10-17T23:00:00Z','PPV','🤼'), ('AEW','Full Gear','2026-11-14T23:00:00Z','PPV','🤼'),
    ('TNA','Bound for Glory','2026-10-11T20:00:00Z','PPV','🤼'),
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
        event={'league':name,'title':title,'start':dt.isoformat().replace('+00:00','Z'),'tag':'UPCOMING','icon':'🏆','source':'official'}
        events.append(event); added+=1
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

def parse_ncaa_time(start_date,start_time):
    if not start_date:return None
    text=re.sub(r'\s+','',str(start_time or '').upper()).replace('ET','')
    if not text:return f'{start_date}T00:00:00Z'
    for fmt in ('%Y-%m-%d%I:%M%p','%Y-%m-%d%H:%M'):
        try:return datetime.strptime(f'{start_date}{text}',fmt).replace(tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc).isoformat().replace('+00:00','Z')
        except ValueError: pass
    return f'{start_date}T00:00:00Z'

def add_ncaa(events,name,sport,division,icon,days=30):
    start=datetime.now(timezone.utc).date(); results=[]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(lambda u: json.loads(get(u)),f'https://ncaa-api.henrygd.me/scoreboard/{sport}/{division}/{start+timedelta(days=i):%Y/%m/%d}/all-conf'):i for i in range(days+1)}
        for f in as_completed(futures):
            try: results.append(f.result())
            except Exception as exc: print(f'ERROR NCAA {name}: {exc}')
    if not results:return False,0
    added=0
    for root in results:
        for wrapper in root.get('games',[]):
            game=wrapper.get('game',wrapper) if isinstance(wrapper,dict) else {}
            away=((game.get('away') or {}).get('names') or {}).get('short') or ((game.get('away') or {}).get('names') or {}).get('full')
            home=((game.get('home') or {}).get('names') or {}).get('short') or ((game.get('home') or {}).get('names') or {}).get('full')
            title=f'{away} @ {home}' if away and home else game.get('title') or name
            state=str(game.get('gameState') or '').lower(); tag='LIVE' if state in ('live','in-progress','in') else ('FINAL' if state in ('final','f') else 'UPCOMING')
            start_at=parse_ncaa_time(game.get('startDate'),game.get('startTime'))
            if start_at: events.append({'league':name,'title':title,'start':start_at,'tag':tag,'icon':icon,'source':'ncaa'}); added+=1
    return True,added

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
    events=[]; failures=[]; counts={}
    official_failures,official_counts=add_official_sources(events)
    # Keep wrestling's specialized parser because WWE/AEW/TNA pages expose useful
    # event markup/text that is not always represented as JSON-LD.
    add_wrestling(events)
    for league in ESPN_LEAGUES:
        ok,n=add_espn(events,*league); counts[league[0]]=n
        if not ok: failures.append(league[0])
    for league in NCAA_LEAGUES:
        ok,n=add_ncaa(events,*league); counts[league[0]]=n
        if not ok: failures.append(league[0])
    previous={}
    if OUT.exists():
        try: previous=json.loads(OUT.read_text(encoding='utf-8'))
        except Exception: previous={}
    prev_events=previous.get('events') or []
    present_leagues={e.get('league') for e in events}
    # Only restore a failed provider's last-good league when no official or other
    # source produced coverage for that league in this refresh.
    for league in failures:
        if league in present_leagues: continue
        events.extend(e for e in prev_events if e.get('league')==league)
        counts[league]=sum(1 for e in events if e.get('league')==league)
    # Official sources win duplicate keys; provider data fills gaps.
    priority={'official':0,'ncaa':1,'espn':2,'fallback':3,None:4}
    unique={}
    for event in events:
        event=event.copy(); source=event.pop('source',None); event['_sourcePriority']=priority.get(source,4)
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
        'officialSourceFailures':official_failures,
        'officialSourceCounts':official_counts,
        'events':events,
    }
    tmp=OUT.with_suffix('.tmp'); tmp.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); tmp.replace(OUT)
    print(f'wrote {len(events)} events across {len(per)} leagues; provider_failures={failures}; official_failures={official_failures}')

if __name__=='__main__':main()
