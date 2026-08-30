#!/usr/bin/env python3
# Schedule publication intentionally keeps every fetched event; do not add a per-league truncation cap.
import json, re, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

OUT = Path('data/schedule_feed.json')
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.espn.com/',
    'Connection': 'keep-alive',
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
    ('WWE','NXT Heatwave','2026-08-30T17:00:00Z','SPECIAL','🏆'), ('WWE',"Sunday Night's Main Event",'2026-09-07T00:00:00Z','SPECIAL','🏆'),
    ('WWE','Worlds Collide','2026-09-27T00:00:00Z','SPECIAL','🏆'), ('WWE','Money in the Bank','2026-10-10T22:00:00Z','PLE','🏆'),
    ('WWE','Survivor Series: WarGames','2026-11-29T00:00:00Z','PLE','🏆'), ('AEW','All In: London','2026-08-30T15:30:00Z','PPV','🤼'),
    ('AEW','All Out','2026-09-26T23:00:00Z','PPV','🤼'), ('AEW','Grand Slam: France','2026-10-06T00:00:00Z','SPECIAL','🤼'),
    ('AEW','WrestleDream','2026-10-17T23:00:00Z','PPV','🤼'), ('AEW','Full Gear','2026-11-14T23:00:00Z','PPV','🤼'),
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

def get_espn(url):
    candidates = [url.replace('https://site.api.espn.com', 'https://site.web.api.espn.com'), url]
    last_error = None
    for target in candidates:
        try: return get(target)
        except Exception as exc:
            last_error = exc
            print(f'ERROR ESPN request {target}: {exc}')
    raise last_error

def add_espn(events, name, sport, league, icon, days):
    start = datetime.now(timezone.utc).date(); end = start + timedelta(days=days)
    url = f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={start:%Y%m%d}-{end:%Y%m%d}&limit=1000'
    try: root = json.loads(get_espn(url))
    except Exception as exc:
        print(f'ERROR ESPN {name}: {exc}'); return False
    for event in root.get('events', []):
        comp = (event.get('competitions') or [{}])[0]; teams = comp.get('competitors') or []
        home = next((x.get('team',{}).get('shortDisplayName') or x.get('team',{}).get('displayName') for x in teams if x.get('homeAway') == 'home'), '')
        away = next((x.get('team',{}).get('shortDisplayName') or x.get('team',{}).get('displayName') for x in teams if x.get('homeAway') == 'away'), '')
        title = f'{away} @ {home}' if home and away else (event.get('name') or event.get('shortName') or name)
        status = ((comp.get('status') or {}).get('type') or {}); state = status.get('state','pre')
        tag = 'LIVE' if state == 'in' else ('FINAL' if state == 'post' else 'UPCOMING')
        start_at = event.get('date')
        if start_at: events.append({'league':name,'title':title,'start':start_at,'tag':tag,'icon':icon})
    return True

def parse_ncaa_time(start_date, start_time):
    if not start_date: return None
    text = str(start_time or '').strip()
    if not text: return f'{start_date}T00:00:00Z'
    text = re.sub(r'\s+', '', text.upper()).replace('ET', '')
    for fmt in ('%Y-%m-%d%I:%M%p', '%Y-%m-%d%H:%M'):
        try:
            dt = datetime.strptime(f'{start_date}{text}', fmt).replace(tzinfo=ZoneInfo('America/New_York'))
            return dt.astimezone(timezone.utc).isoformat().replace('+00:00','Z')
        except ValueError: pass
    return f'{start_date}T00:00:00Z'

def ncaa_day(url):
    try: return json.loads(get(url)), None
    except Exception as exc: return None, str(exc)

def add_ncaa(events, name, sport, division, icon, days=30):
    start = datetime.now(timezone.utc).date(); dates = [start + timedelta(days=i) for i in range(days + 1)]; results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(ncaa_day, f'https://ncaa-api.henrygd.me/scoreboard/{sport}/{division}/{d:%Y/%m/%d}/all-conf'): d for d in dates}
        for future in as_completed(futures):
            root, error = future.result()
            if error: print(f'ERROR NCAA {name} {futures[future]}: {error}'); continue
            results.append(root)
    if not results: return False
    added = 0
    for root in results:
        for wrapper in root.get('games', []):
            game = wrapper.get('game', wrapper) if isinstance(wrapper, dict) else {}
            away = ((game.get('away') or {}).get('names') or {}).get('short') or ((game.get('away') or {}).get('names') or {}).get('full')
            home = ((game.get('home') or {}).get('names') or {}).get('short') or ((game.get('home') or {}).get('names') or {}).get('full')
            title = f'{away} @ {home}' if away and home else game.get('title') or name
            state = str(game.get('gameState') or '').lower(); tag = 'LIVE' if state in ('live','in-progress','in') else ('FINAL' if state in ('final','f') else 'UPCOMING')
            start_at = parse_ncaa_time(game.get('startDate'), game.get('startTime'))
            if start_at: events.append({'league':name,'title':title,'start':start_at,'tag':tag,'icon':icon}); added += 1
    print(f'NCAA {name}: added {added} events'); return True

def jsonld_objects(html):
    for match in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.I | re.S):
        try:
            value = json.loads(match.strip()); values = value if isinstance(value, list) else value.get('@graph', []) if isinstance(value, dict) else []
            if isinstance(value, dict) and value.get('@type'): values = [value] + values
            for obj in values:
                if isinstance(obj, dict): yield obj
        except Exception: continue

def add_official_wrestling(events, brand, url, icon):
    try: html = get(url).decode('utf-8', 'ignore')
    except Exception as exc: print(f'skip official {brand}: {exc}'); return 0
    added = 0; now = datetime.now(timezone.utc) - timedelta(hours=6)
    for obj in jsonld_objects(html):
        kind = obj.get('@type')
        if kind != 'Event' and not (isinstance(kind, list) and 'Event' in kind): continue
        title = str(obj.get('name') or '').strip(); start = str(obj.get('startDate') or '').strip()
        if not title or not start: continue
        if start.endswith('Z'): start_at = start
        else:
            try: start_at = datetime.fromisoformat(start.replace('Z','+00:00')).astimezone(timezone.utc).isoformat().replace('+00:00','Z')
            except Exception: continue
        try: dt = datetime.fromisoformat(start_at.replace('Z','+00:00'))
        except Exception: continue
        if dt < now: continue
        events.append({'league':brand,'title':title,'start':start_at,'tag':'PPV' if any(x in title.lower() for x in ('all in','all out','wrestledream','full gear','bound for glory','money in the bank','survivor series')) else 'SPECIAL','icon':icon}); added += 1
    return added

def add_wrestling(events):
    found = set()
    for brand, url, icon in OFFICIAL_WRESTLING:
        if add_official_wrestling(events, brand, url, icon): found.add(brand)
    for brand,title,start,tag,icon in WRESTLING_FALLBACK:
        if brand not in found and datetime.fromisoformat(start.replace('Z','+00:00')) >= datetime.now(timezone.utc) - timedelta(hours=6):
            events.append({'league':brand,'title':title,'start':start,'tag':tag,'icon':icon})

def main():
    events=[]; failures=[]
    for league in ESPN_LEAGUES:
        if not add_espn(events,*league): failures.append(league[0])
    for league in NCAA_LEAGUES:
        if not add_ncaa(events,*league): failures.append(league[0])
    add_wrestling(events)
    if failures and OUT.exists():
        try:
            previous = json.loads(OUT.read_text(encoding='utf-8')); previous_events = previous.get('events') or []
            if previous_events:
                failed_set = set(failures); events = [e for e in events if e.get('league') not in failed_set]
                events.extend(e for e in previous_events if e.get('league') in failed_set)
                print(f'preserved prior events for failed leagues: {", ".join(failures)}')
        except Exception as exc: print(f'warning: could not preserve prior feed: {exc}')
    unique={}
    for e in events: unique[(e.get('league'), e.get('title'), e.get('start'))]=e
    events=list(unique.values()); events.sort(key=lambda x:x['start'])
    per_league={}
    for event in events: per_league[event['league']] = per_league.get(event['league'], 0) + 1
    # Never truncate a populated league. The previous 400-event cap silently dropped
    # valid future games, especially high-volume NCAA soccer/volleyball schedules.
    selected = list(events)
    payload={'schema':4,'generatedAt':datetime.now(timezone.utc).isoformat(),'refreshHours':6,'eventCounts':per_league,'failedSources':failures,'events':sorted(selected, key=lambda x:x['start'])}
    tmp=OUT.with_suffix('.tmp'); tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False)+'\n', encoding='utf-8'); tmp.replace(OUT)
    print(f'wrote {len(selected)} events across {len(per_league)} leagues to {OUT}')

if __name__ == '__main__': main()
