#!/usr/bin/env python3
"""Hydrate remaining team-sport logo gaps before phase3.

Uses ESPN's public team catalogs/scoreboards to populate the persistent cache for
AFL, NBA, NRL, PLL and UEFA Europa League. This is intentionally upstream of
phase3 so the visual pass remains cache-only and fast.
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

# Known provider-name variants that commonly differ from ESPN display names.
ALIASES = {
    'NBA': {
        'Los Angeles Clippers': 'LA Clippers',
        'Los Angeles Lakers': 'Los Angeles Lakers',
        'LA Lakers': 'Los Angeles Lakers',
        'Golden State': 'Golden State Warriors',
        'New Orleans': 'New Orleans Pelicans',
        'Oklahoma City': 'Oklahoma City Thunder',
    },
    'UEL': {
        'N.E.C.': 'N.E.C.',
        'NEC': 'N.E.C.',
        'NEC Nijmegen': 'N.E.C.',
        'Union Saint-Gilloise': 'Union SG',
        'Union St. Gilloise': 'Union SG',
        'Union Saint Gilloise': 'Union SG',
        'Red Bull Salzburg': 'Salzburg',
        'Salzburg': 'Salzburg',
        'Bayer Leverkusen': 'Leverkusen',
        'H. Beer-Sheva': 'H. Beer-Sheva',
        'Hapoel Be\'er Sheva': 'H. Beer-Sheva',
        'Beşiktaş': 'Beşiktaş',
        'Besiktas': 'Beşiktaş',
        'Viktoria Plzen': 'Viktoria Plzeň',
        'Sparta Prague': 'Sparta Praha',
        'Ferencvaros': 'Ferencváros',
        'Lech Poznan': 'Lech Poznań',
        'Jagiellonia Bialystok': 'Jagiellonia',
        'Lillestrom': 'Lillestrøm',
        'Omonia Nicosia': 'Omonia',
        'GNK Dinamo Zagreb': 'GNK Dinamo',
        'Dinamo Zagreb': 'GNK Dinamo',
        'OFI': 'OFI Crete',
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
    for item in (payload.get('sports') or []):
        for league in (item.get('leagues') or []):
            for wrapper in (league.get('teams') or []):
                team = wrapper.get('team') or wrapper
                if team.get('id') or team.get('displayName'):
                    out.append(team)
    return out


def add_team(teams, league, team, aliases):
    display = team.get('displayName') or team.get('name') or team.get('shortDisplayName')
    if not display:
        return False
    logos = team.get('logos') or []
    logo = None
    for candidate in logos:
        if candidate.get('href'):
            logo = candidate['href']
            break
    if not logo:
        tid = team.get('id')
        if tid:
            logo = f'https://a.espncdn.com/i/teamlogos/{"soccer" if league == "UEL" else league.lower()}/500/{tid}.png'
    if not logo:
        return False
    names = {display, team.get('name'), team.get('shortDisplayName'), team.get('location'), team.get('abbreviation'), team.get('slug')}
    if team.get('location') and team.get('name'):
        names.add(f"{team['location']} {team['name']}")
    canonical = display
    for name in names:
        if name:
            aliases.setdefault(norm(name), logo)
    for alias, target in ALIASES.get(league, {}).items():
        if norm(target) in aliases and norm(target) == norm(canonical):
            aliases[norm(alias)] = logo
    teams[f'{league}|{norm(canonical)}'] = logo
    for alias, target in ALIASES.get(league, {}).items():
        if norm(target) == norm(canonical):
            teams[f'{league}|{norm(alias)}'] = logo
    return True


def hydrate():
    data = json.loads(CACHE.read_text(encoding='utf-8')) if CACHE.exists() else {'version': 3, 'teams': {}}
    teams = data.setdefault('teams', {})
    summary = {}
    for league, (sport, slug) in LEAGUES.items():
        records = []
        urls = [f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/teams?limit=100']
        if league == 'UEL':
            urls.append('https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.europa/scoreboard?limit=1000')
        elif league == 'AFL':
            urls.append('https://site.api.espn.com/apis/site/v2/sports/australian-football/afl/scoreboard?limit=1000')
        elif league == 'NRL':
            urls.append('https://site.api.espn.com/apis/site/v2/sports/rugby-league/nrl/scoreboard?limit=1000')
        elif league == 'PLL':
            urls.append('https://site.api.espn.com/apis/site/v2/sports/lacrosse/pll/scoreboard?limit=1000')
        elif league == 'NBA':
            urls.append('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?limit=1000')
        for url in urls:
            try:
                payload = get_json(url)
            except Exception as exc:
                print(f'WARNING {league}: {url} -> {exc}')
                continue
            records.extend(team_records(payload))
            for event in payload.get('events') or []:
                for comp in (event.get('competitions') or []):
                    for competitor in comp.get('competitors') or []:
                        team = competitor.get('team') or {}
                        if team:
                            records.append(team)
        dedup = {}
        for team in records:
            key = str(team.get('id') or team.get('displayName') or team.get('name') or '')
            if key:
                dedup[key] = team
        alias_cache = {}
        added = 0
        for team in dedup.values():
            if add_team(teams, league, team, alias_cache):
                added += 1
        # Apply schedule-facing aliases after the ESPN catalog is loaded.
        schedule_names = set()
        if SCHEDULE.exists():
            feed = json.loads(SCHEDULE.read_text(encoding='utf-8'))
            for event in feed.get('events') or []:
                if event.get('league') == league:
                    for key in ('away', 'home'):
                        if event.get(key):
                            schedule_names.add(str(event[key]))
        matched = 0
        for name in schedule_names:
            key = f'{league}|{norm(name)}'
            if key in teams:
                matched += 1
                continue
            target = ALIASES.get(league, {}).get(name)
            if target and teams.get(f'{league}|{norm(target)}'):
                teams[key] = teams[f'{league}|{norm(target)}']
                matched += 1
        summary[league] = {'espn_records': len(dedup), 'catalog_writes': added, 'schedule_names': len(schedule_names), 'schedule_names_resolved': matched}
        time.sleep(0.1)
    CACHE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    hydrate()
