#!/usr/bin/env python3
import json, re, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

OUT = Path('data/schedule_feed.json')
HEADERS = {'User-Agent': 'XSportsX-ScheduleBot/1.0', 'Accept': 'application/json,text/html'}

LEAGUES = [
    ('NFL','football','nfl','🏈'), ('NCAA FB','football','college-football','🏈'), ('CFL','football','cfl','🏈'),
    ('NBA','basketball','nba','🏀'), ('WNBA','basketball','wnba','🏀'),
    ('NCAA BB','basketball','mens-college-basketball','🏀'), ('NCAA WBB','basketball','womens-college-basketball','🏀'),
    ('MLB','baseball','mlb','⚾'), ('NCAA Baseball','baseball','college-baseball','⚾'),
    ('NHL','hockey','nhl','🏒'),
    ('MLS','soccer','usa.1','⚽'), ('EPL','soccer','eng.1','⚽'), ('UCL','soccer','uefa.champions','⚽'),
    ('LaLiga','soccer','esp.1','⚽'), ('Serie A','soccer','ita.1','⚽'), ('Bundesliga','soccer','ger.1','⚽'), ('Ligue 1','soccer','fra.1','⚽'),
    ('UFC','mma','ufc','🥊'),
    ('F1','racing','f1','🏎️'), ('IndyCar','racing','irl','🏎️'), ('NASCAR Cup','racing','nascar-premier','🏎️'),
    ('PGA','golf','pga','⛳'), ('LPGA','golf','lpga','⛳'), ('LIV Golf','golf','liv','⛳'),
    ('ATP','tennis','atp','🎾'), ('WTA','tennis','wta','🎾'),
    ('PLL','lacrosse','pll','🥍'), ('NLL','lacrosse','nll','🥍'),
    ('FIVB Men','volleyball','fivb.m','🏐'), ('FIVB Women','volleyball','fivb.w','🏐'),
    ('Rugby World Cup','rugby','164205','🏉'), ('Six Nations','rugby','180659','🏉'),
    ('NRL','rugby-league','3','🏉'), ('AFL','australian-football','afl','🏉'),
    ('ICC T20','cricket','icc.t20','🏏'), ('IPL','cricket','ipl','🏏'),
]

WRESTLING_FALLBACK = [
    ('WWE','NXT Heatwave','2026-08-30T17:00:00Z','SPECIAL','🏆'),
    ('WWE',"Sunday Night's Main Event",'2026-09-07T00:00:00Z','SPECIAL','🏆'),
    ('WWE','Worlds Collide','2026-09-27T00:00:00Z','SPECIAL','🏆'),
    ('WWE','Money in the Bank','2026-10-10T22:00:00Z','PLE','🏆'),
    ('WWE','Survivor Series: WarGames','2026-11-29T00:00:00Z','PLE','🏆'),
    ('AEW','All In: London','2026-08-30T15:30:00Z','PPV','🤼'),
    ('AEW','All Out','2026-09-26T23:00:00Z','PPV','🤼'),
    ('AEW','Grand Slam: France','2026-10-06T00:00:00Z','SPECIAL','🤼'),
    ('AEW','WrestleDream','2026-10-17T23:00:00Z','PPV','🤼'),
    ('AEW','Full Gear','2026-11-14T23:00:00Z','PPV','🤼'),
    ('TNA','Bound for Glory','2026-10-11T20:00:00Z','PPV','🤼'),
]

OFFICIAL_WRESTLING = [
    ('WWE','https://www.wwe.com/article/wwe-upcoming-events','🏆'),
    ('AEW','https://www.allelitewrestling.com/aew-events','🤼'),
    ('TNA','https://tnawrestling.com/events/','🤼'),
]

def get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=12) as r:
        return r.read()

def add_espn(events, name, sport, league, icon):
    start = datetime.now(timezone.utc).date()
    end = start + timedelta(days=14)
    dates = f'{start:%Y%m%d}-{end:%Y%m%d}'
    url = f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={dates}&limit=500'
    try:
        root = json.loads(get(url))
    except Exception as exc:
        print(f'skip {name}: {exc}')
        return
    for event in root.get('events', []):
        comp = (event.get('competitions') or [{}])[0]
        teams = comp.get('competitors') or []
        home = next((x.get('team',{}).get('shortDisplayName') or x.get('team',{}).get('displayName') for x in teams if x.get('homeAway') == 'home'), '')
        away = next((x.get('team',{}).get('shortDisplayName') or x.get('team',{}).get('displayName') for x in teams if x.get('homeAway') == 'away'), '')
        title = f'{away} @ {home}' if home and away else (event.get('name') or event.get('shortName') or name)
        status = ((comp.get('status') or {}).get('type') or {})
        state = status.get('state','pre')
        tag = 'LIVE' if state == 'in' else ('FINAL' if state == 'post' else 'UPCOMING')
        start_at = event.get('date')
        if start_at:
            events.append({'league':name,'title':title,'start':start_at,'tag':tag,'icon':icon})

def jsonld_objects(html):
    for match in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.I | re.S):
        try:
            value = json.loads(match.strip())
            values = value if isinstance(value, list) else value.get('@graph', []) if isinstance(value, dict) else []
            if isinstance(value, dict) and value.get('@type'): values = [value] + values
            for obj in values:
                if isinstance(obj, dict): yield obj
        except Exception:
            continue

def add_official_wrestling(events, brand, url, icon):
    try:
        html = get(url).decode('utf-8', 'ignore')
    except Exception as exc:
        print(f'skip official {brand}: {exc}')
        return 0
    added = 0
    now = datetime.now(timezone.utc) - timedelta(hours=6)
    for obj in jsonld_objects(html):
        kind = obj.get('@type')
        if kind != 'Event' and not (isinstance(kind, list) and 'Event' in kind):
            continue
        title = str(obj.get('name') or '').strip()
        start = str(obj.get('startDate') or '').strip()
        if not title or not start: continue
        if start.endswith('Z'):
            start_at = start
        else:
            try: start_at = datetime.fromisoformat(start.replace('Z','+00:00')).astimezone(timezone.utc).isoformat().replace('+00:00','Z')
            except Exception: continue
        try: dt = datetime.fromisoformat(start_at.replace('Z','+00:00'))
        except Exception: continue
        if dt < now: continue
        events.append({'league':brand,'title':title,'start':start_at,'tag':'PPV' if any(x in title.lower() for x in ('all in','all out','wrestledream','full gear','bound for glory','money in the bank','survivor series')) else 'SPECIAL','icon':icon})
        added += 1
    return added

def add_wrestling(events):
    found = set()
    for brand, url, icon in OFFICIAL_WRESTLING:
        count = add_official_wrestling(events, brand, url, icon)
        if count: found.add(brand)
    for brand,title,start,tag,icon in WRESTLING_FALLBACK:
        if brand not in found and datetime.fromisoformat(start.replace('Z','+00:00')) >= datetime.now(timezone.utc) - timedelta(hours=6):
            events.append({'league':brand,'title':title,'start':start,'tag':tag,'icon':icon})

def main():
    events=[]
    for league in LEAGUES:
        add_espn(events,*league)
    add_wrestling(events)
    events.sort(key=lambda x:x['start'])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload={'schema':2,'generatedAt':datetime.now(timezone.utc).isoformat(),'refreshHours':6,'events':events[:600]}
    tmp=OUT.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    tmp.replace(OUT)
    print(f'wrote {len(events)} events to {OUT}')

if __name__ == '__main__': main()
