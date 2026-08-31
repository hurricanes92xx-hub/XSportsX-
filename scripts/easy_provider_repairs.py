#!/usr/bin/env python3
"""Small, low-risk provider repairs that run after the canonical refresh.

These adapters only add data when a source returns a real schedule and never delete
existing events. Official league schedules are preferred where ESPN coverage is
incomplete, with ESPN retained as a fallback.
"""
from __future__ import annotations
import json
import re
import subprocess
import tempfile
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

FEED = Path('data/schedule_feed.json')
HEADERS = {'User-Agent': 'XSportsX-Schedule/5.4', 'Accept': 'application/json,text/plain,*/*'}

TARGETS = [
    ('NWSL', 'soccer', 'usa.nwsl', '⚽', 45),
    ('UEL', 'soccer', 'uefa.europa', '⚽', 120),
]


def fetch(url: str, headers=None):
    req = urllib.request.Request(url, headers=headers or HEADERS)
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


def fetch_json(url: str):
    return json.loads(fetch(url).decode('utf-8', 'ignore'))


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
            root = fetch_json(url)
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


def add_official_cfl(events):
    """Parse the CFL's published 2026 ET schedule PDF.

    CFL.ca is the authoritative schedule and ESPN's CFL scoreboard can return no
    usable events even while the league is active. The PDF is linked from the
    official schedule page and is deliberately preferred for CFL.
    """
    page_url = 'https://www.cfl.ca/schedule/'
    page = fetch(page_url, {'User-Agent': HEADERS['User-Agent'], 'Accept': 'text/html,*/*'})
    html = page.decode('utf-8', 'ignore')
    pdfs = re.findall(r'https?://[^\"\' ]+\.pdf|(?:href|src)=[\"\']([^\"\']+\.pdf)', html, flags=re.I)
    candidates = []
    for item in pdfs:
        url = item if item.startswith('http') else urllib.parse.urljoin(page_url, item)
        if 'cfl' in url.lower() and 'schedule' in url.lower():
            candidates.append(url)
    candidates += [
        'https://static.cfl.ca/wp-content/uploads/CFL-2026-Schedule-ET-.pdf',
        'https://static.cfl.ca/wp-content/uploads/CFL-2026-Schedule-ET--1.pdf',
    ]

    pdf = None
    chosen = None
    for url in candidates:
        try:
            data = fetch(url, {'User-Agent': HEADERS['User-Agent'], 'Accept': 'application/pdf,*/*'})
            if data.startswith(b'%PDF'):
                pdf, chosen = data, url
                break
        except Exception as exc:
            print(f'WARNING official CFL PDF {url}: {exc}')
    if not pdf:
        print('NO REPAIR CFL: official CFL schedule PDF unavailable')
        return 0

    with tempfile.TemporaryDirectory() as td:
        pdf_path = Path(td) / 'cfl.pdf'
        txt_path = Path(td) / 'cfl.txt'
        pdf_path.write_bytes(pdf)
        try:
            subprocess.run(['pdftotext', '-layout', str(pdf_path), str(txt_path)], check=True, timeout=30)
            text = txt_path.read_text(encoding='utf-8', errors='ignore')
        except Exception as exc:
            print(f'WARNING official CFL PDF parse failed ({chosen}): {exc}')
            return 0

    # ET schedule lines look like: THU JUN 4 | 7:30 PM ET | MTL @ HAM.
    # The PDF repeats week headings, so collect date/time/team triplets without
    # relying on fixed page positions.
    months = 'JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC'
    line_re = re.compile(
        rf'(?P<dow>MON|TUE|WED|THU|FRI|SAT|SUN)\s+(?P<mon>{months})\s+(?P<day>\d{{1,2}})\s+'
        rf'(?P<time>\d{{1,2}}:\d{{2}}\s+(?:AM|PM))\s*(?:ET)?\s*'
        rf'(?P<away>[A-Z]{{2,3}})\s*@\s*(?P<home>[A-Z]{{2,3}})', re.I)

    existing = {(e.get('league'), e.get('title'), e.get('start')) for e in events}
    added = 0
    year = datetime.now(timezone.utc).year
    for m in line_re.finditer(text):
        try:
            dt = datetime.strptime(
                f"{year} {m.group('mon').upper()} {int(m.group('day'))} {m.group('time').upper()}",
                '%Y %b %d %I:%M %p',
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        title = f"{m.group('away').upper()} @ {m.group('home').upper()}"
        start = dt.isoformat().replace('+00:00', 'Z')
        key = ('CFL', title, start)
        if key in existing:
            continue
        events.append({'league': 'CFL', 'title': title, 'start': start, 'tag': 'UPCOMING', 'icon': '🏈', 'source': 'cfl.ca'})
        existing.add(key)
        added += 1
    print(f'OFFICIAL CFL schedule: added {added} events from {chosen}')
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

    cfl_added = add_official_cfl(events)
    report['CFL'] = {'source': 'CFL.ca official schedule PDF', 'added': cfl_added}
    if cfl_added:
        official_failures = [x for x in official_failures if x != 'CFL']
        provider_failures = [x for x in provider_failures if x != 'CFL']
    else:
        print('NO REPAIR CFL: official schedule produced no events')

    payload['events'] = events
    payload['officialSourceFailures'] = official_failures
    payload['failedSources'] = provider_failures
    payload['eventCounts'] = {k: sum(1 for e in events if e.get('league') == k) for k in sorted({e.get('league') for e in events if e.get('league')})}
    payload['generatedAt'] = datetime.now(timezone.utc).isoformat()
    FEED.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'easy provider repairs complete: {len(events)} total events across {len(payload["eventCounts"])} leagues')


if __name__ == '__main__':
    main()
