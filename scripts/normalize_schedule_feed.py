#!/usr/bin/env python3
"""Normalize provider output into the stable app-facing schedule contract."""
import json
from pathlib import Path
from event_identity import event_identity, normalize_league, SPORT_BY_LEAGUE

FEED = Path('data/schedule_feed.json')

def sport_for(league, event):
    key = normalize_league(league)
    return SPORT_BY_LEAGUE.get(key) or str(event.get('sport') or '').strip().lower() or 'other'

def main():
    data = json.loads(FEED.read_text(encoding='utf-8'))
    events = data.get('events') or []
    normalized = []
    for event in events:
        if not isinstance(event, dict):
            continue
        e = dict(event)
        start = e.get('startUtc') or e.get('start')
        if not start:
            continue
        e['startUtc'] = str(start)
        e['start'] = e['startUtc']
        e['league'] = str(e.get('league') or 'Unknown').strip()
        e['sport'] = sport_for(e['league'], e)
        e['title'] = str(e.get('title') or '').strip()
        e['id'] = event_identity(e['league'], e['title'], e['startUtc'], e.get('home'), e.get('away'))
        normalized.append(e)
    normalized.sort(key=lambda e: e.get('startUtc', ''))
    data['events'] = normalized
    data['schema'] = 8
    data['eventCounts'] = {}
    for e in normalized:
        data['eventCounts'][e['league']] = data['eventCounts'].get(e['league'], 0) + 1
    FEED.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Normalized canonical contract: {len(normalized)} events')

if __name__ == '__main__':
    main()
