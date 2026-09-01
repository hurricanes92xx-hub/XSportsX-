#!/usr/bin/env python3
"""Build and audit dedicated NCAA hockey/field-hockey team catalogs.

The generic NCAA logo hydrator is intentionally supplemented here because these
three sports have different competitive universes and frequent schedule-name
variants. ESPN supplies IDs/logos; the schedule feed supplies the names that
must resolve at presentation time.
"""
from __future__ import annotations
import json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / 'data' / 'schedule_feed.json'
LOGOS = ROOT / 'data' / 'team_logo_map.json'
OUT = ROOT / 'data' / 'ncaa_hockey_field_hockey_catalog_audit.json'
HEADERS = {'User-Agent': 'XSportsX-NCAA-Catalog-Audit/1.0', 'Accept': 'application/json'}

LEAGUES = {
    "NCAA Women's Field Hockey": ('field-hockey', 'womens-college-field-hockey', 'ncaa_field_hockey_team_catalog.json'),
    "NCAA Men's Hockey": ('hockey', 'mens-college-hockey', 'ncaa_mens_hockey_team_catalog.json'),
    "NCAA Women's Hockey": ('hockey', 'womens-college-hockey', 'ncaa_womens_hockey_team_catalog.json'),
}

def norm(value: str) -> str:
    value = str(value or '').upper()
    value = re.sub(r'&', ' AND ', value)
    value = re.sub(r'[^A-Z0-9]+', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()

def get_json(url: str):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode('utf-8', 'ignore'))

def extract(root):
    groups = []
    for sport in (root.get('sports') or []) if isinstance(root, dict) else []:
        for league in sport.get('leagues') or []:
            groups.extend(league.get('teams') or [])
    if not groups and isinstance(root, dict):
        groups = root.get('teams') or []
    rows = []
    seen = set()
    for item in groups:
        team = item.get('team') if isinstance(item, dict) else item
        if not isinstance(team, dict):
            continue
        logos = team.get('logos') or []
        logo = ''
        for entry in logos:
            if isinstance(entry, dict) and entry.get('href'):
                logo = str(entry['href']).strip(); break
        aliases = []
        for key in ('displayName', 'shortDisplayName', 'name', 'abbreviation', 'slug'):
            value = str(team.get(key) or '').strip()
            if value and value not in aliases:
                aliases.append(value)
        team_id = str(team.get('id') or '').strip()
        identity = team_id or (aliases[0] if aliases else '')
        if not identity or identity in seen:
            continue
        seen.add(identity)
        rows.append({'id': team_id, 'displayName': aliases[0] if aliases else '', 'aliases': aliases, 'logo': logo, 'slug': str(team.get('slug') or '').strip(), 'source': 'ESPN'})
    return rows

def load_feed_names():
    feed = json.loads(FEED.read_text(encoding='utf-8'))
    names = {league: set() for league in LEAGUES}
    for event in feed.get('events') or []:
        league = event.get('league')
        if league not in names or event.get('eventType') not in (None, 'team_game'):
            continue
        for key in ('home', 'away', 'homeTeam', 'awayTeam'):
            value = event.get(key)
            if isinstance(value, dict): value = value.get('displayName') or value.get('name') or value.get('shortDisplayName')
            if value: names[league].add(str(value).strip())
        title = str(event.get('title') or '')
        # Do not infer team names from free-form titles; home/away fields are authoritative.
    return feed, names

def main():
    feed, schedule_names = load_feed_names()
    report = {'generatedAt': datetime.now(timezone.utc).isoformat(), 'leagues': {}, 'overall': {}}
    for league, (sport, slug, filename) in LEAGUES.items():
        url = f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/teams?limit=1000'
        try:
            rows = extract(get_json(url)); error = None
        except Exception as exc:
            rows = []; error = str(exc)
        aliases = {}
        for row in rows:
            for alias in row['aliases']:
                aliases.setdefault(norm(alias), row)
        unmatched = []
        for name in sorted(schedule_names[league]):
            if norm(name) not in aliases:
                unmatched.append(name)
        no_logo = [r['displayName'] for r in rows if not r['logo']]
        duplicate_norms = {}
        for row in rows:
            for alias in row['aliases']:
                duplicate_norms.setdefault(norm(alias), []).append(row['displayName'])
        duplicates = {k: sorted(set(v)) for k, v in duplicate_norms.items() if len(set(v)) > 1}
        catalog = {'version': 1, 'league': league, 'sport': sport, 'slug': slug, 'source': url, 'generatedAt': report['generatedAt'], 'teamCount': len(rows), 'teams': rows}
        (ROOT / 'data' / filename).write_text(json.dumps(catalog, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
        report['leagues'][league] = {
            'endpoint': url, 'catalogTeams': len(rows), 'scheduleTeams': len(schedule_names[league]),
            'matchedScheduleTeams': len(schedule_names[league]) - len(unmatched),
            'unmatchedScheduleTeams': unmatched, 'missingLogoCatalogTeams': sorted(no_logo),
            'duplicateNormalizedAliases': duplicates, 'error': error,
            'catalogFile': f'data/{filename}',
        }
    total_schedule = sum(v['scheduleTeams'] for v in report['leagues'].values())
    total_unmatched = sum(len(v['unmatchedScheduleTeams']) for v in report['leagues'].values())
    total_no_logo = sum(len(v['missingLogoCatalogTeams']) for v in report['leagues'].values())
    report['overall'] = {'leagues': len(LEAGUES), 'scheduleTeamNames': total_schedule, 'unmatchedScheduleTeamNames': total_unmatched, 'catalogTeamsMissingLogos': total_no_logo}
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(report['overall'], sort_keys=True))
    for league, value in report['leagues'].items():
        print(f'{league}: catalog={value["catalogTeams"]}; schedule={value["scheduleTeams"]}; unmatched={len(value["unmatchedScheduleTeams"])}; no_logo={len(value["missingLogoCatalogTeams"])}')
    if any(v['error'] for v in report['leagues'].values()):
        raise SystemExit('One or more NCAA hockey/field-hockey catalogs failed to load')

if __name__ == '__main__':
    main()
