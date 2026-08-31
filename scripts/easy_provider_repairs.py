#!/usr/bin/env python3
"""Small, low-risk provider repairs that run after the canonical refresh.

These adapters only add data when ESPN returns a real scoreboard and never delete
existing events. They also clear an official-source warning when a healthy fallback
actually supplied the league.
"""
from __future__ import annotations
import json
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

FEED = Path('data/schedule_feed.json')
HEADERS = {'User-Agent': 'XSportsX-Schedule/5.4', 'Accept': 'application/json,text/plain,*/*'}

TARGETS = [
    ('NWSL', 'soccer', 'usa.nwsl', '⚽', 45),
    ('UEL', 'soccer', 'uefa.europa', '⚽', 120),
    ('CFL', 'football', 'cfl', '🏈', 60),
]


def fetch(url: str):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode('utf-8', 'ignore'))


def add_scoreboard(events, name, sport, league, icon, days):
    start = datetime.now(timezone.utc).date()
    end = start + timedelta(days=days)
    urls = [
        f'https://site.web.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={start:%Y%m%d}-{end:%Y%m%d}&limit=1000',
        f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={start:%Y%m%d}-{end:%Y%m%d}&limit=1000',
    ]
    root = None
    for url in urls:
        try:
            root = fetch(url)
            break
        except Exception as exc:
            print(f'WARNING easy ESPN {name}: {exc}')
    if not isinstance(root, dict) or not isinstance(root.get('events'), list):
        return 0

    existing = {(e.get('league'), e.get('title'), e.get('start')) for e in events}
    added = 0
    for event in root['events']:
        if not isinstance(event, dict) or not event.get('date'):
            continue
        comp = (event.get('competitions') or [{}])[0]
        teams = comp.get('competitors') or []
        home = next((x.get('team', {}).get('shortDisplayName') or x.get('team', {}).get('displayName') for x in teams if x.get('homeAway') == 'home'), '')
        away = next((x.get('team', {}).get('shortDisplayName') or x.get('team', {}).get('displayName') for x in teams if x.get('homeAway') == 'away'), '')
        title = f'{away} @ {home}' if home and away else (event.get('name') or event.get('shortName') or name)
        status = ((comp.get('status') or {}).get('type') or {}).get('state', 'pre')
        tag = 'LIVE' if status == 'in' else ('FINAL' if status == 'post' else 'UPCOMING')
        row = {'league': name, 'title': title, 'start': event['date'], 'tag': tag, 'icon': icon, 'source': 'espn'}
        key = (name, title, event['date'])
        if key not in existing:
            events.append(row)
            existing.add(key)
            added += 1
    return added


def main():
    payload = json.loads(FEED.read_text(encoding='utf-8'))
    events = payload.get('events') or []
    report = payload.setdefault('providerRepairReport', {})
    official_failures = list(payload.get('officialSourceFailures') or [])
    provider_failures = list(payload.get('failedSources') or [])

    for name, sport, league, icon, days in TARGETS:
        added = add_scoreboard(events, name, sport, league, icon, days)
        report[name] = {'source': 'ESPN scoreboard', 'added': added}
        if added:
            official_failures = [x for x in official_failures if x != name]
            provider_failures = [x for x in provider_failures if x != name]
            print(f'REPAIRED {name}: added {added} ESPN events')
        else:
            print(f'NO REPAIR {name}: ESPN returned no usable events')

    payload['events'] = events
    payload['officialSourceFailures'] = official_failures
    payload['failedSources'] = provider_failures
    payload['eventCounts'] = {k: sum(1 for e in events if e.get('league') == k) for k in sorted({e.get('league') for e in events if e.get('league')})}
    payload['generatedAt'] = datetime.now(timezone.utc).isoformat()
    FEED.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'easy provider repairs complete: {len(events)} total events across {len(payload["eventCounts"])} leagues')


if __name__ == '__main__':
    main()
