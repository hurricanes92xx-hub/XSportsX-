#!/usr/bin/env python3
import json, re, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

OUT = Path('data/schedule_feed.json')
HEADERS = {'User-Agent': 'XSportsX-ScheduleBot/1.0', 'Accept': 'application/json,text/html'}

# Reliable ESPN scoreboard feeds for mainstream leagues. Empty feeds are skipped,
# so one unavailable league can never erase the rest of the catalog.
LEAGUES = [
    ('NFL','football','nfl','🏈'), ('NCAA FB','football','college-football','🏈'),
    ('NBA','basketball','nba','🏀'), ('WNBA','basketball','wnba','🏀'),
    ('NCAA BB','basketball','mens-college-basketball','🏀'), ('NCAA WBB','basketball','womens-college-basketball','🏀'),
    ('MLB','baseball','mlb','⚾'), ('NCAA BBall','baseball','college-baseball','⚾'),
    ('NHL','hockey','nhl','🏒'), ('MLS','soccer','usa.1','⚽'), ('EPL','soccer','eng.1','⚽'),
    ('UCL','soccer','uefa.champions','⚽'), ('LaLiga','soccer','esp.1','⚽'), ('Serie A','soccer','ita.1','⚽'),
    ('Bundesliga','soccer','ger.1','⚽'), ('Ligue 1','soccer','fra.1','⚽'),
    ('UFC','mma','ufc','🥊'), ('F1','racing','f1','🏎️'),
]

WRESTLING = [
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
        home = next((x.get('team',{}).get('shortDisplayName') or x.get('team',{}).get('displayName') for x in teams if x.get('homeAway') == 'home'), 'TBD')
        away = next((x.get('team',{}).get('shortDisplayName') or x.get('team',{}).get('displayName') for x in teams if x.get('homeAway') == 'away'), 'TBD')
        status = ((comp.get('status') or {}).get('type') or {})
        state = status.get('state','pre')
        tag = 'LIVE' if state == 'in' else ('FINAL' if state == 'post' else 'UPCOMING')
        start_at = event.get('date')
        if not start_at: continue
        events.append({'league':name,'title':f'{away} @ {home}','start':start_at,'tag':tag,'icon':icon})

def main():
    events=[]
    for league in LEAGUES:
        add_espn(events,*league)
    for brand,title,start,tag,icon in WRESTLING:
        if datetime.fromisoformat(start.replace('Z','+00:00')) >= datetime.now(timezone.utc) - timedelta(hours=6):
            events.append({'league':brand,'title':title,'start':start,'tag':tag,'icon':icon})
    events.sort(key=lambda x:x['start'])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload={'schema':2,'generatedAt':datetime.now(timezone.utc).isoformat(),'refreshHours':6,'events':events[:400]}
    tmp=OUT.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    tmp.replace(OUT)
    print(f'wrote {len(events)} events to {OUT}')

if __name__ == '__main__': main()
