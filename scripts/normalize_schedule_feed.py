"""Normalize provider output into the stable app-facing schedule contract."""
import json
from pathlib import Path
from event_identity import event_identity, normalize_league, SPORT_BY_LEAGUE

FEED = Path('data/schedule_feed.json')
UFC_PARIS_PRELIMS = '2026-09-05T16:00:00Z'
UFC_PARIS_MAIN = '2026-09-05T19:00:00Z'


def sport_for(league, event):
    key = normalize_league(league)
    return SPORT_BY_LEAGUE.get(key) or str(event.get('sport') or '').strip().lower() or 'other'


def normalize_ufc_event(event):
    """Prevent provider drift from turning one UFC card into duplicate/made-up sessions."""
    if str(event.get('league') or '').strip().upper() != 'UFC':
        return event
    title = str(event.get('title') or '').strip()
    low = title.lower()
    if 'hooker' not in low or 'parnasse' not in low:
        return event
    # UFC Paris has two official broadcast blocks: Prelims 12 PM ET and Main Card 3 PM ET.
    # There is no Early Prelims block, and the individual Hooker/Parnasse bout must not
    # become a third schedule entity beside its containing Main Card.
    if 'early prelim' in low:
        return None
    if 'main card' in low:
        event['title'] = 'UFC Fight Night: Hooker vs Parnasse — Main Card'
        event['startUtc'] = UFC_PARIS_MAIN
        event['start'] = UFC_PARIS_MAIN
        event['session'] = 'Main Card'
        event.setdefault('broadcast', 'Paramount+')
        return event
    if 'prelims' in low:
        event['title'] = 'UFC Fight Night: Hooker vs Parnasse — Prelims'
        event['startUtc'] = UFC_PARIS_PRELIMS
        event['start'] = UFC_PARIS_PRELIMS
        event['session'] = 'Prelims'
        event.setdefault('broadcast', 'Paramount+')
        return event
    return None


def main():
    data = json.loads(FEED.read_text(encoding='utf-8'))
    events = data.get('events') or []
    normalized = []
    for event in events:
        if not isinstance(event, dict):
            continue
        e = dict(event)
        e = normalize_ufc_event(e)
        if e is None:
            continue
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
    # Final identity pass after sport-specific canonicalization. This also collapses
    # duplicate provider records that arrived with different providerEventIds.
    by_id = {}
    for event in normalized:
        key = str(event['id'])
        existing = by_id.get(key)
        if existing is None:
            by_id[key] = event
        else:
            # Preserve a live/explicit provider state and richer metadata when duplicates collide.
            for k, v in event.items():
                if v not in (None, '') and existing.get(k) in (None, ''):
                    existing[k] = v
            if str(event.get('tag') or '').upper() == 'LIVE':
                existing.update({k: v for k, v in event.items() if k in ('tag', 'status', 'state', 'provider_shortDetail', 'provider_detail', 'provider_displayClock', 'provider_period') and v not in (None, '')})
    normalized = list(by_id.values())
    normalized.sort(key=lambda e: e.get('startUtc', ''))
    data['events'] = normalized
    data['schema'] = 8
    data['eventCounts'] = {}
    for e in normalized:
        data['eventCounts'][e['league']] = data['eventCounts'].get(e['league'], 0) + 1
    FEED.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Normalized canonical contract: {len(normalized)} events')

if __name__ == '__main__': main()
