#!/usr/bin/env python3
import json, re, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

OUT = Path('data/schedule_feed.json')
HEADERS = {'User-Agent': 'XSportsX-ScheduleBot/1.1', 'Accept': 'application/json,text/html'}

# ESPN exposes college sports as separate sport/league pairs. Keep these
# explicit instead of treating NCAA as one generic competition. College
# schedules are seasonal, so they get a longer look-ahead window below.
LEAGUES = [
    ('NFL','football','nfl','🏈',14), ('NCAA FB','football','college-football','🏈',60), ('CFL','football','cfl','🏈',30),
    ('NBA','basketball','nba','🏀',30), ('WNBA','basketball','wnba','🏀',30),
    ('NCAA BB','basketball','mens-college-basketball','🏀',180), ('NCAA WBB','basketball','womens-college-basketball','🏀',180),
    ('MLB','baseball','mlb','⚾',30), ('NCAA Baseball','baseball','college-baseball','⚾',180),
    ('NCAA Softball','baseball','college-softball','🥎',180),
    ('NHL','hockey','nhl','🏒',30),
    ('NCAA Men's Hockey','hockey','mens-college-hockey','🏒',180),
    ('NCAA Women's Hockey','hockey','womens-college-hockey','🏒',180),
    ('MLS','soccer','usa.1','⚽',30), ('EPL','soccer','eng.1','⚽',30), ('UCL','soccer','uefa.champions','⚽',30),
    ('LaLiga','soccer','esp.1','⚽',30), ('Serie A','soccer','ita.1','⚽',30), ('Bundesliga','soccer','ger.1','⚽',30), ('Ligue 1','soccer','fra.1','⚽',30),
    ('NCAA Men's Soccer','soccer','usa.ncaa.m.1','⚽',180), ('NCAA Women's Soccer','soccer','usa.ncaa.w.1','⚽',180),
    ('NCAA Men's Lacrosse','lacrosse','mens-college-lacrosse','🥍',180), ('NCAA Women's Lacrosse','lacrosse','womens-college-lacrosse','🥍',180),
    ('NCAA Men's Volleyball','volleyball','mens-college-volleyball','🏐',180), ('NCAA Women's Volleyball','volleyball','womens-college-volleyball','🏐',180),
    ('NCAA Men's Water Polo','water-polo','mens-college-water-polo','🤽',180), ('NCAA Women's Water Polo','water-polo','womens-college-water-polo','🤽',180),
    ('NCAA Women's Field Hockey','field-hockey','womens-college-field-hockey','🏑',180),
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

def add_espn(events, name, sport, league, icon, days):
    start = datetime.now(timezone.utc).date()
    end = start + timedelta(days=days)
    dates = f'{start:%Y%m%d}-{end:%Y%m%d}'
    url = f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={dates}&limit=5000'
    try:
        root = json.loads(get(url))
    except Exception as exc:
        print(f'ERROR {name}: {exc}')
        return False

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
    return True

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
    failures=[]
    for league in LEAGUES:
        ok = add_espn(events,*league)
        if not ok:
            failures.append(league[0])
    add_wrestling(events)

    # Never replace a known-good feed because one upstream provider had a
    # transient failure. This is especially important for college schedules,
    # where many separate ESPN league endpoints are queried.
    if failures and OUT.exists():
        try:
            previous = json.loads(OUT.read_text(encoding='utf-8'))
            previous_events = previous.get('events') or []
            if previous_events:
                failed_prefixes = tuple(failures)
                events = [e for e in events if not str(e.get('league','')).startswith(failed_prefixes)]
                events.extend(e for e in previous_events if str(e.get('league','')) in failures)
                print(f'preserved {len(previous_events)} prior events for failed leagues: {", ".join(failures)}')
        except Exception as exc:
            print(f'warning: could not preserve prior feed: {exc}')

    # Keep a healthy, broad feed. Do not apply one global 600-event cap that
    # lets high-volume football/basketball crowd out smaller college sports.
    events.sort(key=lambda x:x['start'])
    per_league = {}
    for event in events:
        per_league[event['league']] = per_league.get(event['league'], 0) + 1
    selected=[]
    for league_name in sorted(per_league, key=lambda n: min(x['start'] for x in events if x['league']==n)):
        league_events=[x for x in events if x['league']==league_name]
        selected.extend(league_events[:400])

    payload={
        'schema':4,
        'generatedAt':datetime.now(timezone.utc).isoformat(),
        'refreshHours':6,
        'eventCounts':per_league,
        'failedSources':failures,
        'events':sorted(selected, key=lambda x:x['start'])
    }
    tmp=OUT.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    tmp.replace(OUT)
    print(f'wrote {len(selected)} events across {len(per_league)} leagues to {OUT}')

if __name__ == '__main__': main()
