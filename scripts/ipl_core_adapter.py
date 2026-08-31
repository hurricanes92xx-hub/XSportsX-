#!/usr/bin/env python3
"""Recover IPL schedules from a stable fixture source.

ESPN's IPL scoreboard/Core endpoints have repeatedly returned 404/400 from the
GitHub runner. FixtureDownload publishes the IPL season fixture as a normal
HTML table and also exposes the same fixture as JSON/CSV. We use the public
fixture page as the primary schedule source and keep this adapter season-aware.
"""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

FEED = Path('data/schedule_feed.json')
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36',
    'Accept': 'text/html,application/json;q=0.9,*/*;q=0.8',
}


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read().decode('utf-8', 'ignore')


def clean(value: str) -> str:
    value = re.sub(r'<[^>]+>', ' ', value or '')
    value = unescape(value)
    return re.sub(r'\s+', ' ', value).strip()


def parse_fixture_page(html: str, year: int):
    """Parse FixtureDownload's IPL results table without external packages."""
    # Restrict parsing to table rows and accept the published columns:
    # Round, Date, Location, Home Team, Away Team, Result.
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, flags=re.I | re.S)
    out = []
    for raw in rows:
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', raw, flags=re.I | re.S)
        cells = [clean(c) for c in cells]
        if len(cells) < 5:
            continue
        # Skip header/navigation rows.
        if cells[0].lower() in {'round', 'match'} or 'home team' in ' '.join(c.lower() for c in cells):
            continue
        date_text, home, away = cells[1], cells[3], cells[4]
        if not home or not away or home.lower() in {'home team', 'tbd'}:
            continue
        # FixtureDownload renders local/UTC date-time as dd/mm/YYYY HH:MM.
        dt = None
        for fmt in ('%d/%m/%Y %H:%M', '%d/%m/%Y'):
            try:
                dt = datetime.strptime(date_text, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                pass
        if dt is None or dt.year != year:
            continue
        out.append({
            'league': 'IPL',
            'title': f'{away} @ {home}',
            'start': dt.isoformat().replace('+00:00', 'Z'),
            'tag': 'FINAL' if len(cells) >= 6 and cells[5] and cells[5] != '-' else 'UPCOMING',
            'icon': '🏏',
            'source': 'fixturedownload',
        })
    return out


def main():
    payload = json.loads(FEED.read_text(encoding='utf-8'))
    events = payload.get('events') or []
    existing = {(e.get('league'), e.get('title'), e.get('start')) for e in events}
    year = datetime.now(timezone.utc).year

    # FixtureDownload has a predictable season page and publishes the same
    # fixture in JSON/CSV. The HTML table is intentionally used here so the
    # adapter needs no third-party Python dependency or API key.
    url = f'https://fixturedownload.com/results/ipl-{year}'
    added = 0
    source_ok = False
    failures = 0
    try:
        html = fetch_text(url)
        rows = parse_fixture_page(html, year)
        source_ok = bool(rows)
    except Exception as exc:
        failures += 1
        rows = []
        print(f'ERROR IPL FixtureDownload: {exc}')

    for row in rows:
        key = (row['league'], row['title'], row['start'])
        if key in existing:
            continue
        events.append(row)
        existing.add(key)
        added += 1

    payload['events'] = events
    payload['eventCounts'] = {
        k: sum(1 for e in events if e.get('league') == k)
        for k in sorted({e.get('league') for e in events if e.get('league')})
    }
    report = payload.setdefault('providerRepairReport', {})
    report['IPL'] = {
        'source': 'FixtureDownload IPL season page',
        'season': year,
        'added': added,
        'parsed': len(rows),
        'request_failures': failures,
    }

    if source_ok:
        payload['officialSourceFailures'] = [x for x in payload.get('officialSourceFailures', []) if x != 'IPL']
        payload['failedSources'] = [x for x in payload.get('failedSources', []) if x != 'IPL']
        print(f'REPAIRED IPL: FixtureDownload source healthy; parsed={len(rows)}, added={added}')
    else:
        print(f'NO REPAIR IPL: FixtureDownload returned no usable {year} fixtures')

    payload['generatedAt'] = datetime.now(timezone.utc).isoformat()
    FEED.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
