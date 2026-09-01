#!/usr/bin/env python3
"""Build deterministic NCAA hockey/field-hockey catalogs from ESPN scoreboard data.

The ESPN /teams endpoint is incomplete for these sports (especially field hockey).
The scoreboard endpoint contains the actual participating teams, IDs and logos, so
it is the authoritative runtime universe for the schedule horizon. We still use the
teams endpoint when available, but merge scoreboard competitors over it and persist
schedule-name aliases so presentation does not depend on live discovery later.
"""
from __future__ import annotations
import json, re, urllib.request
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / 'data' / 'schedule_feed.json'
OUT = ROOT / 'data' / 'ncaa_hockey_field_hockey_catalog_audit.json'
HEADERS = {'User-Agent': 'XSportsX-NCAA-Catalog-Audit/2.0', 'Accept': 'application/json'}
NOW = datetime.now(timezone.utc)
HORIZON = NOW + timedelta(days=370)

LEAGUES = {
    "NCAA Women's Field Hockey": ('field-hockey', 'womens-college-field-hockey', 'ncaa_field_hockey_team_catalog.json'),
    "NCAA Men's Hockey": ('hockey', 'mens-college-hockey', 'ncaa_mens_hockey_team_catalog.json'),
    "NCAA Women's Hockey": ('hockey', 'womens-college-hockey', 'ncaa_womens_hockey_team_catalog.json'),
}

# Known naming differences in the women’s National Collegiate universe.
EXPLICIT_ALIASES = {
    "ASSUMPTION COLLEGE": "ASSUMPTION",
    "ASSUMPTION COLLEGE GREYHOUNDS": "ASSUMPTION GREYHOUNDS",
    "DELAWARE": "DELAWARE BLUE HENS",
    "LONG ISLAND UNIVERSITY LONG ISLAND UNIVERSITY": "LONG ISLAND UNIVERSITY SHARKS",
    "MINNESOTA ST": "MINNESOTA STATE MAVERICKS",
    "POST UNIVERSITY": "POST EAGLES",
    "POST UNIVERSITY EAGLES": "POST EAGLES",
    "ST ANSELM": "SAINT ANSELM HAWKS",
    "ST ANSELM HAWKS": "SAINT ANSELM HAWKS",
    "UNION NY": "UNION GARNET CHARGERS",
    "UNION NY GARNET CHARGERS": "UNION GARNET CHARGERS",
}

def norm(value: str) -> str:
    value = str(value or '').upper().replace('&', ' AND ')
    value = re.sub(r'[^A-Z0-9]+', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()

def get_json(url: str):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode('utf-8', 'ignore'))

def extract_team_rows(root):
    groups = []
    if isinstance(root, dict):
        for sport in root.get('sports') or []:
            for league in sport.get('leagues') or []:
                groups.extend(league.get('teams') or [])
        if not groups:
            groups = root.get('teams') or []
    rows = []
    seen = set()
    for item in groups:
        team = item.get('team') if isinstance(item, dict) else item
        if not isinstance(team, dict):
            continue
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
        logo = ''
        for entry in team.get('logos') or []:
            if isinstance(entry, dict) and entry.get('href'):
                logo = str(entry['href']).strip(); break
        rows.append({'id': team_id, 'displayName': aliases[0] if aliases else '', 'aliases': aliases, 'logo': logo, 'slug': str(team.get('slug') or '').strip(), 'source': 'ESPN'})
    return rows

def parse_title(title: str):
    text = str(title or '').strip()
    for pattern in (r'^(.+?)\s+@\s+(.+)$', r'^(.+?)\s+AT\s+(.+)$', r'^(.+?)\s+(?:VS\.?|VERSUS)\s+(.+)$'):
        match = re.match(pattern, text, re.I)
        if match:
            return match.group(1).strip(), match.group(2).strip()
    return '', ''

def load_feed_names():
    feed = json.loads(FEED.read_text(encoding='utf-8'))
    names = {league: set() for league in LEAGUES}
    for event in feed.get('events') or []:
        league = event.get('league')
        if league not in names or event.get('eventType') not in (None, 'team_game'):
            continue
        values = []
        for key in ('home', 'away', 'homeTeam', 'awayTeam'):
            value = event.get(key)
            if isinstance(value, dict):
                value = value.get('displayName') or value.get('name') or value.get('shortDisplayName')
            if value:
                values.append(str(value).strip())
        if len(values) < 2:
            away, home = parse_title(event.get('title'))
            values.extend([v for v in (away, home) if v])
        names[league].update(v for v in values if v and norm(v) not in {'TBD', 'TBA'})
    return feed, names

def scoreboard_rows(sport: str, slug: str):
    rows = {}
    cursor = NOW.date()
    while cursor <= HORIZON.date():
        end = min(cursor + timedelta(days=29), HORIZON.date())
        url = f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/scoreboard?dates={cursor:%Y%m%d}-{end:%Y%m%d}&limit=1000'
        try:
            root = get_json(url)
        except Exception:
            cursor = end + timedelta(days=1)
            continue
        for event in root.get('events') or []:
            competition = (event.get('competitions') or [{}])[0]
            for competitor in competition.get('competitors') or []:
                team = competitor.get('team') or {}
                team_id = str(team.get('id') or '').strip()
                aliases = []
                for key in ('displayName', 'shortDisplayName', 'name', 'abbreviation', 'slug'):
                    value = str(team.get(key) or '').strip()
                    if value and value not in aliases:
                        aliases.append(value)
                if not team_id and not aliases:
                    continue
                identity = team_id or aliases[0]
                logo = ''
                for entry in team.get('logos') or []:
                    if isinstance(entry, dict) and entry.get('href'):
                        logo = str(entry['href']).strip(); break
                if not logo and team_id:
                    logo = f'https://a.espncdn.com/i/teamlogos/ncaa/500/{team_id}.png'
                row = rows.get(identity, {'id': team_id, 'displayName': aliases[0] if aliases else '', 'aliases': [], 'logo': '', 'slug': str(team.get('slug') or '').strip(), 'source': 'ESPN scoreboard'})
                for alias in aliases:
                    if alias not in row['aliases']:
                        row['aliases'].append(alias)
                if logo:
                    row['logo'] = logo
                rows[identity] = row
        cursor = end + timedelta(days=1)
    return list(rows.values())

def best_row(name, rows):
    target = norm(name)
    explicit = EXPLICIT_ALIASES.get(target)
    candidates = rows
    if explicit:
        candidates = [r for r in rows if any(norm(a) == explicit for a in r['aliases'])] or rows
    for row in candidates:
        if target in {norm(a) for a in row['aliases']}:
            return row
    target_tokens = set(target.split())
    best = None; best_score = 0.0
    for row in candidates:
        for alias in row['aliases']:
            value = norm(alias)
            tokens = set(value.split())
            overlap = len(target_tokens & tokens) / max(1, len(target_tokens | tokens))
            ratio = SequenceMatcher(None, target, value).ratio()
            score = max(ratio, overlap * 0.92)
            if target and (target in value or value in target):
                score = max(score, 0.84)
            if score > best_score:
                best_score = score; best = row
    return best if best_score >= 0.62 else None

def main():
    feed, schedule_names = load_feed_names()
    report = {'generatedAt': datetime.now(timezone.utc).isoformat(), 'leagues': {}, 'overall': {}}
    for league, (sport, slug, filename) in LEAGUES.items():
        endpoint = f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/teams?limit=1000'
        try:
            base_rows = extract_team_rows(get_json(endpoint))
            endpoint_error = None
        except Exception as exc:
            base_rows = []; endpoint_error = str(exc)
        scoreboard = scoreboard_rows(sport, slug)
        merged = {}
        for row in base_rows + scoreboard:
            key = row.get('id') or norm(row.get('displayName'))
            if not key:
                continue
            current = merged.get(key, {'id': row.get('id',''), 'displayName': row.get('displayName',''), 'aliases': [], 'logo': '', 'slug': row.get('slug',''), 'source': row.get('source','ESPN')})
            for alias in row.get('aliases') or []:
                if alias and alias not in current['aliases']:
                    current['aliases'].append(alias)
            if row.get('displayName') and not current['displayName']:
                current['displayName'] = row['displayName']
            if row.get('logo'):
                current['logo'] = row['logo']
            if row.get('slug'):
                current['slug'] = row['slug']
            current['source'] = 'ESPN scoreboard' if row.get('source') == 'ESPN scoreboard' else current['source']
            merged[key] = current
        rows = list(merged.values())
        # Persist every schedule spelling as an alias on the best canonical row.
        unmatched = []
        alias_matches = {}
        for name in sorted(schedule_names[league]):
            row = best_row(name, rows)
            if row is None:
                unmatched.append(name)
            else:
                if name not in row['aliases']:
                    row['aliases'].append(name)
                alias_matches[name] = row['displayName']
        no_logo = sorted({r['displayName'] for r in rows if not r.get('logo') and r.get('displayName')})
        duplicate_normalized = {}
        for row in rows:
            for alias in row['aliases']:
                duplicate_normalized.setdefault(norm(alias), []).append(row['displayName'])
        duplicates = {k: sorted(set(v)) for k, v in duplicate_normalized.items() if len(set(v)) > 1}
        catalog = {'version': 2, 'league': league, 'sport': sport, 'slug': slug, 'source': endpoint, 'scheduleSource': 'ESPN scoreboard', 'generatedAt': report['generatedAt'], 'teamCount': len(rows), 'teams': rows}
        (ROOT / 'data' / filename).write_text(json.dumps(catalog, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
        report['leagues'][league] = {'endpoint': endpoint, 'scoreboardSource': f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/scoreboard', 'catalogTeams': len(rows), 'scheduleTeams': len(schedule_names[league]), 'matchedScheduleTeams': len(schedule_names[league]) - len(unmatched), 'unmatchedScheduleTeams': unmatched, 'scheduleAliasMatches': alias_matches, 'missingLogoCatalogTeams': no_logo, 'duplicateNormalizedAliases': duplicates, 'endpointError': endpoint_error, 'scoreboardTeams': len(scoreboard), 'catalogFile': f'data/{filename}'}
    report['overall'] = {'leagues': len(LEAGUES), 'scheduleTeamNames': sum(v['scheduleTeams'] for v in report['leagues'].values()), 'unmatchedScheduleTeamNames': sum(len(v['unmatchedScheduleTeams']) for v in report['leagues'].values()), 'catalogTeamsMissingLogos': sum(len(v['missingLogoCatalogTeams']) for v in report['leagues'].values()), 'scoreboardTeams': sum(v['scoreboardTeams'] for v in report['leagues'].values())}
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(report['overall'], sort_keys=True))
    for league, value in report['leagues'].items():
        print(f'{league}: catalog={value["catalogTeams"]}; scoreboard={value["scoreboardTeams"]}; schedule={value["scheduleTeams"]}; unmatched={len(value["unmatchedScheduleTeams"])}; no_logo={len(value["missingLogoCatalogTeams"])}')
    if report['overall']['unmatchedScheduleTeamNames']:
        raise SystemExit('Unmatched NCAA hockey/field-hockey schedule names remain')

if __name__ == '__main__':
    main()
