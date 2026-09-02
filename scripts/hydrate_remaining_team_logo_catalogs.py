#!/usr/bin/env python3
"""Hydrate and apply remaining team-sport logos before/after the visual pass.

Uses ESPN public team catalogs/scoreboards to populate the persistent cache for
AFL, NBA, NRL, PLL and UEFA Europa League. The script also repairs the existing
feed directly so a post-refresh repair can close gaps without regenerating the
schedule.
"""
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'data/team_logo_map.json'
SCHEDULE = ROOT / 'data/schedule_feed.json'

LEAGUES = {
    'AFL': ('australian-football', 'afl'),
    'NBA': ('basketball', 'nba'),
    'NRL': ('rugby-league', 'nrl'),
    'PLL': ('lacrosse', 'pll'),
    'UEL': ('soccer', 'uefa.europa'),
}

ALIASES = {
    'NBA': {
        'Los Angeles Clippers': 'LA Clippers',
        'LA Lakers': 'Los Angeles Lakers',
        'Golden State': 'Golden State Warriors',
        'New Orleans': 'New Orleans Pelicans',
        'Oklahoma City': 'Oklahoma City Thunder',
    },
    'UEL': {
        'N.E.C.': 'N.E.C.', 'NEC': 'N.E.C.', 'NEC Nijmegen': 'N.E.C.',
        'Union Saint-Gilloise': 'Union SG', 'Union St. Gilloise': 'Union SG',
        'Union Saint Gilloise': 'Union SG', 'Red Bull Salzburg': 'Salzburg',
        'Bayer Leverkusen': 'Leverkusen', 'H. Beer-Sheva': 'H. Beer-Sheva',
        'Hapoel Be\'er Sheva': 'H. Beer-Sheva', 'Besiktas': 'Beşiktaş',
        'Viktoria Plzen': 'Viktoria Plzeň', 'Sparta Prague': 'Sparta Praha',
        'Ferencvaros': 'Ferencváros', 'Lech Poznan': 'Lech Poznań',
        'Jagiellonia Bialystok': 'Jagiellonia', 'Lillestrom': 'Lillestrøm',
        'Omonia Nicosia': 'Omonia', 'GNK Dinamo Zagreb': 'GNK Dinamo',
        'Dinamo Zagreb': 'GNK Dinamo', 'OFI': 'OFI Crete',
    },
}


def norm(value):
    return ' '.join(re.sub(r'[^A-Z0-9]+', ' ', str(value or '').upper()).split())


def get_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'XSportsX/1.0'})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode('utf-8'))


def team_records(payload):
    out = []
    for item in payload.get('sports') or []:
        for league in item.get('leagues') or []:
            for wrapper in league.get('teams') or []:
                team = wrapper.get('team') or wrapper
                if team.get('id') or team.get('displayName'):
                    out.append(team)
    return out


def logo_for(team):
    for candidate in team.get('logos') or []:
        if candidate.get('href'):
            return candidate['href']
    tid = team.get('id')
    return f'https://a.espncdn.com/i/teamlogos/500/{tid}.png' if tid else None


def add_team(teams, league, team):
    display = team.get('displayName') or team.get('name') or team.get('shortDisplayName')
    logo = logo_for(team)
    if not display or not logo:
        return False
    names = {display, team.get('name'), team.get('shortDisplayName'), team.get('location'), team.get('abbreviation'), team.get('slug')}
    if team.get('location') and team.get('name'):
        names.add(f"{team['location']} {team['name']}")
    for name in names:
        if name:
            teams[f'{league}|{norm(name)}'] = logo
    for alias, target in ALIASES.get(league, {}).items():
        if norm(target) == norm(display):
            teams[f'{league}|{norm(alias)}'] = logo
    return True


def catalog_for_league(league, sport, slug):
    records = []
    urls = [f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/teams?limit=100']
    urls.append(f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/scoreboard?limit=1000')
    for url in urls:
        try:
            payload = get_json(url)
        except Exception as exc:
            print(f'WARNING {league}: {exc}')
            continue
        records.extend(team_records(payload))
        for event in payload.get('events') or []:
            for comp in event.get('competitions') or []:
                for competitor in comp.get('competitors') or []:
                    team = competitor.get('team') or {}
                    if team:
                        records.append(team)
    dedup = {}
    for team in records:
        key = str(team.get('id') or team.get('displayName') or team.get('name') or '')
        if key:
            dedup[key] = team
    return list(dedup.values())


def hydrate_and_apply():
    data = json.loads(CACHE.read_text(encoding='utf-8')) if CACHE.exists() else {'version': 3, 'teams': {}}
    teams = data.setdefault('teams', {})
    feed = json.loads(SCHEDULE.read_text(encoding='utf-8'))
    events = feed.get('events') or []
    summary = {}
    for league, (sport, slug) in LEAGUES.items():
        records = catalog_for_league(league, sport, slug)
        for team in records:
            add_team(teams, league, team)
        # Schedule-facing aliases.
        names = {str(e.get(k)) for e in events if e.get('league') == league for k in ('away', 'home') if e.get(k)}
        for name in names:
            key = f'{league}|{norm(name)}'
            if key not in teams:
                target = ALIASES.get(league, {}).get(name)
                if target and teams.get(f'{league}|{norm(target)}'):
                    teams[key] = teams[f'{league}|{norm(target)}']
        changed = 0
        unresolved = []
        for event in events:
            if event.get('league') != league or event.get('eventType') == 'named_event':
                continue
            for side, field in (('away', 'awayLogo'), ('home', 'homeLogo')):
                name = str(event.get(side) or '')
                logo = teams.get(f'{league}|{norm(name)}')
                if not logo:
                    unresolved.append(name)
                    continue
                if event.get(field) != logo:
                    event[field] = logo
                    changed += 1
        summary[league] = {
            'espn_records': len(records),
            'schedule_names': len(names),
            'unresolved_names': sorted(set(unresolved)),
            'logo_fields_changed': changed,
        }
        time.sleep(0.1)
    CACHE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    feed['events'] = events
    feed['generatedAt'] = feed.get('generatedAt')
    SCHEDULE.write_text(json.dumps(feed, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    failures = {k: v['unresolved_names'] for k, v in summary.items() if v['unresolved_names']}
    if failures:
        print('UNRESOLVED:', json.dumps(failures, ensure_ascii=False))
    return summary


if __name__ == '__main__':
    hydrate_and_apply()
