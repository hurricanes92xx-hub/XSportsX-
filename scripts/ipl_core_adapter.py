#!/usr/bin/env python3
"""Recover IPL schedules through ESPN's cricket Core API.

Cricket does not expose a usable Site API scoreboard. ESPN's documented public
Core collection is the supported event source. Keep this adapter independent
of the normal scoreboard/date-window path so offseason IPL does not create a
false provider failure and the next season can be discovered automatically.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

FEED = Path('data/schedule_feed.json')
BASE = 'https://sports.core.api.espn.com/v2/sports/cricket/leagues/ipl/events'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36',
    'Accept': 'application/json,text/plain,*/*',
}


def fetch_json(url: str):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode('utf-8', 'ignore'))


def event_from_item(item):
    if not isinstance(item, dict):
        return None
    if 'date' in item and ('competitions' in item or 'name' in item):
        return item
    ref = item.get('$ref')
    if not ref:
        return None
    # ESPN sometimes emits an internal .pvt host in Core $ref values.
    ref = ref.replace('sports.core.api.espn.pvt', 'sports.core.api.espn.com')
    try:
        return fetch_json(ref)
    except Exception as exc:
        print(f'WARNING IPL Core event fetch failed: {exc}')
        return None


def parse_event(event):
    if not isinstance(event, dict) or not event.get('date'):
        return None
    competitions = event.get('competitions') or []
    comp = competitions[0] if competitions else {}
    competitors = comp.get('competitors') or []
    home = next((c.get('team', {}).get('shortDisplayName') or c.get('team', {}).get('displayName')
                 for c in competitors if c.get('homeAway') == 'home'), '')
    away = next((c.get('team', {}).get('shortDisplayName') or c.get('team', {}).get('displayName')
                 for c in competitors if c.get('homeAway') == 'away'), '')
    title = f'{away} @ {home}' if home and away else (event.get('name') or event.get('shortName') or 'IPL')
    status = ((comp.get('status') or {}).get('type') or {}).get('state', 'pre')
    tag = 'LIVE' if status in {'in', 'live'} else ('FINAL' if status in {'post', 'closed'} else 'UPCOMING')
    return {
        'league': 'IPL',
        'title': title,
        'start': event['date'],
        'tag': tag,
        'icon': '🏏',
        'source': 'espn-core',
    }


def main():
    payload = json.loads(FEED.read_text(encoding='utf-8'))
    events = payload.get('events') or []
    existing = {(e.get('league'), e.get('title'), e.get('start')) for e in events}

    # Do NOT send a dates range here. The IPL Core collection accepts the
    # collection paging parameters; the prior dates=YYYYMMDD-YYYYMMDD request
    # was rejected with HTTP 400 by ESPN. Historical/current collection data is
    # useful for keeping the feed populated, while the canonical feed's normal
    # season intelligence controls what the UI considers in-season.
    next_url = f'{BASE}?limit=100'
    pages = 0
    added = 0
    resolved = 0
    failures = 0

    while next_url and pages < 20:
        pages += 1
        try:
            root = fetch_json(next_url)
        except Exception as exc:
            failures += 1
            print(f'ERROR ESPN Core IPL page {pages}: {exc}')
            break

        for item in root.get('items') or []:
            event = event_from_item(item)
            if event is None:
                continue
            resolved += 1
            row = parse_event(event)
            if not row:
                continue
            key = (row['league'], row['title'], row['start'])
            if key in existing:
                continue
            events.append(row)
            existing.add(key)
            added += 1

        page = root.get('page') or {}
        next_url = page.get('next')
        if next_url:
            next_url = next_url.replace('sports.core.api.espn.pvt', 'sports.core.api.espn.com')

    payload['events'] = events
    payload['eventCounts'] = {
        k: sum(1 for e in events if e.get('league') == k)
        for k in sorted({e.get('league') for e in events if e.get('league')})
    }
    report = payload.setdefault('providerRepairReport', {})
    report['IPL'] = {
        'source': 'ESPN cricket Core API',
        'added': added,
        'resolved': resolved,
        'pages': pages,
        'request_failures': failures,
    }

    # A successful collection request is a healthy source even during the
    # IPL offseason. Only mark IPL healthy when ESPN actually answered with a
    # valid collection; don't manufacture a failure from zero in-season games.
    if pages > 0 and failures == 0:
        payload['officialSourceFailures'] = [x for x in payload.get('officialSourceFailures', []) if x != 'IPL']
        payload['failedSources'] = [x for x in payload.get('failedSources', []) if x != 'IPL']
        print(f'IPL Core source healthy: added={added}, resolved={resolved}, pages={pages}')
    else:
        print(f'NO REPAIR IPL: Core collection unavailable (pages={pages}, failures={failures})')

    payload['generatedAt'] = datetime.now(timezone.utc).isoformat()
    FEED.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
