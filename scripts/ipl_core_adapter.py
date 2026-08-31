#!/usr/bin/env python3
"""Recover IPL schedules through ESPN's cricket Core API.

ESPN's cricket site scoreboard endpoint returns 404 for IPL. The public Core API
is the supported path for cricket event collections, so this adapter discovers
IPL events there and normalizes them into the canonical schedule feed.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

FEED = Path('data/schedule_feed.json')
HEADERS = {
    'User-Agent': 'XSportsX-Schedule/5.4',
    'Accept': 'application/json,text/plain,*/*',
}


def fetch_json(url: str):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode('utf-8', 'ignore'))


def event_from_item(item):
    if not isinstance(item, dict):
        return None
    # Core collections normally return {$ref: ...}. Some responses can expose
    # the event object inline, so accept either form.
    if 'date' in item and ('competitions' in item or 'name' in item):
        return item
    ref = item.get('$ref')
    if not ref:
        return None
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
    year = datetime.now(timezone.utc).year
    # IPL is normally played in the spring. Use the current season year; this
    # keeps the adapter season-aware and avoids hard-coding 2026 forever.
    start = f'{year}0101'
    end = f'{year}1231'
    url = f'https://sports.core.api.espn.com/v2/sports/cricket/leagues/ipl/events?dates={start}-{end}&limit=1000'

    try:
        root = fetch_json(url)
    except Exception as exc:
        print(f'ERROR ESPN Core IPL: {exc}')
        print('NO REPAIR IPL: ESPN Core API unavailable')
        return

    items = root.get('items') or []
    added = 0
    resolved = 0
    for item in items:
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

    # The collection may paginate. Follow the documented next-page link when
    # present, while keeping a hard cap so a malformed response cannot loop.
    next_url = (root.get('page') or {}).get('next')
    pages = 0
    while next_url and pages < 10:
        pages += 1
        try:
            page = fetch_json(next_url)
        except Exception as exc:
            print(f'WARNING ESPN Core IPL next page failed: {exc}')
            break
        for item in page.get('items') or []:
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
        next_url = (page.get('page') or {}).get('next')

    payload['events'] = events
    payload['eventCounts'] = {
        k: sum(1 for e in events if e.get('league') == k)
        for k in sorted({e.get('league') for e in events if e.get('league')})
    }
    report = payload.setdefault('providerRepairReport', {})
    report['IPL'] = {'source': 'ESPN cricket Core API', 'added': added, 'resolved': resolved}

    if added:
        payload['officialSourceFailures'] = [x for x in payload.get('officialSourceFailures', []) if x != 'IPL']
        payload['failedSources'] = [x for x in payload.get('failedSources', []) if x != 'IPL']
        print(f'REPAIRED IPL: added {added} ESPN Core events (resolved={resolved})')
    else:
        print(f'NO REPAIR IPL: Core API returned no new events (resolved={resolved})')

    payload['generatedAt'] = datetime.now(timezone.utc).isoformat()
    FEED.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
