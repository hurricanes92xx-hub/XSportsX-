#!/usr/bin/env python3
# Legacy provider primitives retained behind the league-provider matrix.
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
HEADERS = {'User-Agent':'XSportsX-Schedule/3.3','Accept':'application/json, text/html, */*','Accept-Language':'en-US,en;q=0.9'}
# ESPN is used as a keyless shadow for fragile/blocked dedicated feeds.  The
# primary provider is still allowed to win through the provider matrix.
ESPN_LEAGUES = [('NFL','football','nfl','🏈',14),('CFL','football','cfl','🏈',30),('NBA','basketball','nba','🏀',30),('WNBA','basketball','wnba','🏀',30),('NHL','hockey','nhl','🏒',30),('NCAA Women\'s Hockey','hockey','womens-college-hockey','🏒',180),('MLB','baseball','mlb','⚾',30),('MLS','soccer','usa.1','⚽',30),('EPL','soccer','eng.1','⚽',30),('UCL','soccer','uefa.champions','⚽',30),('LaLiga','soccer','esp.1','⚽',30),('Serie A','soccer','ita.1','⚽',30),('Bundesliga','soccer','ger.1','⚽',30),('Ligue 1','soccer','fra.1','⚽',30),('UFC','mma','ufc','🥊',30),('F1','racing','f1','🏎️',30),('IndyCar','racing','irl','🏎️',30),('NASCAR Truck','racing','nascar-truck','🏎️',30),('X Games','action-sports','xgames','🏆',30),('PGA','golf','pga','⛳',30),('LPGA','golf','lpga','⛳',30),('LIV Golf','golf','liv','⛳',30),('ATP','tennis','atp','🎾',30),('WTA','tennis','wta','🎾',30),('PLL','lacrosse','pll','🥍',30),('NLL','lacrosse','nll','🥍',30),('FIVB Men','volleyball','fivb.m','🏐',30),('FIVB Women','volleyball','fivb.w','🏐',30),('Rugby World Cup','rugby','164205','🏉',30),('Six Nations','rugby','180659','🏉',30),('NRL','rugby-league','3','🏉',30),('AFL','australian-football','afl','🏉',30),('ICC T20','cricket','icc.t20','🏏',30),('IPL','cricket','ipl','🏏',30)]
WRESTLING_FALLBACK=[('WWE','SmackDown','2026-09-05T00:00:00Z','SPECIAL','🏆'),('WWE',"Sunday Night's Main Event",'2026-09-07T00:00:00Z','SPECIAL','🏆'),('AAA Wrestling','AAA Lucha Libre','2026-09-06T02:00:00Z','SPECIAL','🏆'),('WWE','Monday Night Raw','2026-09-08T00:00:00Z','SPECIAL','🏆'),('WWE','Monday Night Raw','2026-09-14T00:00:00Z','SPECIAL','🏆'),('WWE','Monday Night Raw','2026-09-21T00:00:00Z','SPECIAL','🏆'),('WWE','Monday Night Raw','2026-09-28T00:00:00Z','SPECIAL','🏆'),('WWE','Monday Night Raw','2026-10-05T00:00:00Z','SPECIAL','🏆'),('WWE','Monday Night Raw','2026-10-12T00:00:00Z','SPECIAL','🏆'),('WWE','Monday Night Raw','2026-10-19T00:00:00Z','SPECIAL','🏆'),('WWE','Monday Night Raw','2026-10-26T00:00:00Z','SPECIAL','🏆'),('WWE','Monday Night Raw','2026-11-02T00:00:00Z','SPECIAL','🏆'),('WWE','NXT Heatwave','2026-08-30T17:00:00Z','SPECIAL','🏆'),('WWE','Worlds Collide','2026-09-26T00:00:00Z','PLE','🏆'),('WWE','Money in the Bank','2026-10-10T22:00:00Z','PLE','🏆'),('WWE','Survivor Series: WarGames','2026-11-29T00:00:00Z','PLE','🏆'),('AEW','All In: London','2026-08-30T15:30:00Z','PPV','🤼'),('AEW','All Out','2026-09-26T23:00:00Z','PPV','🤼'),('AEW','Grand Slam: France','2026-10-06T00:00:00Z','SPECIAL','🤼'),('AEW','WrestleDream','2026-10-17T23:00:00Z','PPV','🤼'),('AEW','Full Gear','2026-11-14T23:00:00Z','PPV','🤼'),('TNA','Bound for Glory','2026-10-11T20:00:00Z','PPV','🤼')]
OFFICIAL_WRESTLING=[('WWE','https://www.wwe.com/article/wwe-upcoming-events','🏆'),('AEW','https://www.allelitewrestling.com/aew-events','🤼'),('TNA','https://tnawrestling.com/events/','🤼'),('AAA Wrestling','https://www.wwe.com/shows/aaa','🏆')]

def get(url):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=12) as r:return r.read()
def load_official_registry():
    try:return json.loads(OFFICIAL_REGISTRY.read_text(encoding='utf-8')).get('officialSources') or []
    except Exception:return []
def parse_iso(value):
    if not value:return None
    try:return datetime.fromisoformat(str(value).replace('Z','+00:00')).astimezone(timezone.utc)
    except Exception:return None
def jsonld_objects(html):
    for m in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',html,re.I|re.S):
        try:
            v=json.loads(m.strip());vals=v if isinstance(v,list) else ([v] if isinstance(v,dict) and v.get('@type') else [])
            if isinstance(v,dict) and isinstance(v.get('@graph'),list):vals.extend(v['@graph'])
            for o in vals:
                if isinstance(o,dict):yield o
        except Exception:continue
def add_official_source(events,source):
    name=str(source.get('league') or '').strip();url=str(source.get('url') or '').strip()
    if not name or not url:return False,0
    try:html=get(url).decode('utf-8','ignore')
    except Exception as exc:print(f'ERROR official {name}: {exc}');return False,0
    added=0;now=datetime.now(timezone.utc)-timedelta(hours=12);horizon=datetime.now(timezone.utc)+timedelta(days=370)
    for obj in jsonld_objects(html):
        kind=obj.get('@type');dt=parse_iso(obj.get('startDate'));title=str(obj.get('name') or '').strip()
        if (kind=='Event' or (isinstance(kind,list) and 'Event' in kind)) and title and dt and now<=dt<=horizon:
            events.append({'league':name,'title':title,'start':dt.isoformat().replace('+00:00','Z'),'tag':'UPCOMING','icon':'🏆','source':'official'});added+=1
    return True,added
def get_espn(url):
    last=None
    for target in (url.replace('https://site.api.espn.com','https://site.web.api.espn.com'),url):
        try:return get(target)
        except Exception as exc:last=exc;print(f'ERROR ESPN request {target}: {exc}')
    raise last
def add_espn(events,name,sport,league,icon,days):
    start=datetime.now(timezone.utc).date();end=start+timedelta(days=days);url=f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={start:%Y%m%d}-{end:%Y%m%d}&limit=1000'
    try:root=json.loads(get_espn(url))
    except Exception as exc:print(f'ERROR ESPN {name}: {exc}');return False,0
    raw=root.get('events');
    if not isinstance(raw,list):return False,0
    for event in raw:
        comp=(event.get('competitions') or [{}])[0];teams=comp.get('competitors') or []
        h=next((x.get('team',{}).get('shortDisplayName') or x.get('team',{}).get('displayName') for x in teams if x.get('homeAway')=='home'),'');a=next((x.get('team',{}).get('shortDisplayName') or x.get('team',{}).get('displayName') for x in teams if x.get('homeAway')=='away'),'')
        if not event.get('date'):continue
        state=((comp.get('status') or {}).get('type') or {}).get('state','pre');e={'league':name,'title':f'{a} @ {h}' if h and a else (event.get('name') or event.get('shortName') or name),'start':event['date'],'tag':'LIVE' if state=='in' else ('FINAL' if state=='post' else 'UPCOMING'),'icon':icon,'source':'espn'}
        if h:e['home']=h
        if a:e['away']=a
        if event.get('id'):e['providerEventId']=f'espn:{event["id"]}'
        for side,key in [('home','homeTeamId'),('away','awayTeamId')]:
            team=next((x.get('team',{}) for x in teams if x.get('homeAway')==side),{})
            if team.get('id'):e[key]=str(team['id'])
        events.append(e)
    return True,len(raw)
def add_sportsdb(events,name,icon):
    if name not in SPORTDB_LEAGUES:return False,0
    raw=fetch_league(name,current_season())
    if not raw:return False,0
    for event in raw:event['icon']=icon;events.append(event)
    return True,len(raw)
def add_wrestling(events):
    found=set()
    for brand,url,icon in OFFICIAL_WRESTLING:
        try:html=get(url).decode('utf-8','ignore')
        except Exception:continue
        for o in jsonld_objects(html):
            dt=parse_iso(o.get('startDate'));title=str(o.get('name') or '').strip();kind=o.get('@type')
            if (kind=='Event' or (isinstance(kind,list) and 'Event' in kind)) and title and dt and dt>=datetime.now(timezone.utc)-timedelta(hours=6):events.append({'league':brand,'title':title,'start':dt.isoformat().replace('+00:00','Z'),'tag':'SPECIAL','icon':icon,'source':'official'});found.add((brand,title,dt.strftime('%Y-%m-%d')))
    for brand,title,start,tag,icon in WRESTLING_FALLBACK:
        dt=parse_iso(start);key=(brand,title,dt.strftime('%Y-%m-%d')) if dt else None
        if dt and key not in found and dt>=datetime.now(timezone.utc)-timedelta(hours=6):events.append({'league':brand,'title':title,'start':start,'tag':tag,'icon':icon,'source':'fallback'})
