#!/usr/bin/env python3
"""Build a canonical NCAA Division I non-football school identity catalog.

The catalog is intentionally independent of NCAA football. A school can have
many valid college sports and logos while having no football program.
"""
from __future__ import annotations
import json, re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / 'data' / 'ncaa_nonfootball_school_catalog.json'
LOGOS = ROOT / 'data' / 'team_logo_map.json'
OUT = ROOT / 'data' / 'ncaa_nonfootball_identity_catalog.json'

SPORT_PRIORITY = [
    "NCAA BB", "NCAA WBB", "NCAA Men's Volleyball", "NCAA Women's Volleyball",
    "NCAA Men's Soccer", "NCAA Women's Soccer", "NCAA Men's Hockey", "NCAA Women's Hockey",
    "NCAA Women's Field Hockey", "NCAA Baseball", "NCAA Softball", "NCAA Men's Lacrosse",
    "NCAA Women's Lacrosse", "NCAA Wrestling", "NCAA Gymnastics", "NCAA Swimming & Diving",
    "NCAA Track & Field", "NCAA Men's Golf", "NCAA Women's Golf",
]
ALIAS = {
    "IU Indy": ["IU Indy", "IU Indianapolis", "Indiana University Indianapolis", "IUPUI", "Indiana Indianapolis"],
    "Kansas City": ["Kansas City", "UMKC", "Missouri Kansas City", "Kansas City Roos"],
    "Queens (NC)": ["Queens", "Queens NC", "Queens University of Charlotte"],
    "Green Bay": ["Green Bay", "Wisconsin Green Bay", "UW Green Bay"],
    "Cal State Bakersfield": ["Cal State Bakersfield", "CSU Bakersfield", "Cal State-Bakersfield"],
    "Cal State Fullerton": ["Cal State Fullerton", "CSU Fullerton"],
    "Cal State Northridge": ["Cal State Northridge", "CSUN"],
    "California Baptist": ["California Baptist", "Cal Baptist", "CBU"],
    "Fairleigh Dickinson": ["Fairleigh Dickinson", "FDU"],
    "Florida Gulf Coast": ["Florida Gulf Coast", "FGCU"],
    "George Mason": ["George Mason", "GMU"],
    "Grand Canyon": ["Grand Canyon", "GCU"],
    "Le Moyne": ["Le Moyne", "LeMoyne"],
    "LSU New Orleans": ["LSU New Orleans", "New Orleans", "UNO"],
    "Maryland Eastern Shore": ["Maryland Eastern Shore", "UMES"],
    "Mount St. Mary's": ["Mount St Mary's", "Mount St. Marys", "Mount St. Mary's"],
    "NJIT": ["NJIT", "New Jersey Institute of Technology"],
    "Northern Kentucky": ["Northern Kentucky", "NKU"],
    "Oral Roberts": ["Oral Roberts", "ORU"],
    "Purdue Fort Wayne": ["Purdue Fort Wayne", "Fort Wayne", "PFW"],
    "SIU Edwardsville": ["SIU Edwardsville", "SIUE", "Southern Illinois Edwardsville"],
    "South Carolina Upstate": ["South Carolina Upstate", "USC Upstate"],
    "Southern Indiana": ["Southern Indiana", "USI"],
    "Texas A&M-Corpus Christi": ["Texas A&M Corpus Christi", "Texas A&M-Corpus Christi", "TAMUCC", "Corpus Christi"],
    "UC Riverside": ["UC Riverside", "UCR", "Cal Riverside"],
    "UC Irvine": ["UC Irvine", "UCI"],
    "UC San Diego": ["UC San Diego", "UCSD"],
    "UC Santa Barbara": ["UC Santa Barbara", "UCSB"],
    "UIC": ["UIC", "Illinois Chicago", "University of Illinois Chicago"],
    "UMass Lowell": ["UMass Lowell", "Massachusetts Lowell", "UML"],
    "UMBC": ["UMBC", "Maryland Baltimore County"],
    "UNC Asheville": ["UNC Asheville", "North Carolina Asheville", "UNCA"],
    "UNC Greensboro": ["UNC Greensboro", "UNCG", "North Carolina Greensboro"],
    "UNC Wilmington": ["UNC Wilmington", "UNCW", "North Carolina Wilmington"],
    "UT Arlington": ["UT Arlington", "UTA", "Texas Arlington"],
    "Utah Valley": ["Utah Valley", "UVU"],
    "VCU": ["VCU", "Virginia Commonwealth"],
    "Wichita State": ["Wichita State", "WSU"],
}

def norm(s: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'[^A-Z0-9]+', ' ', str(s or '').upper())).strip()

def aliases_for(school: str) -> set[str]:
    vals = {school, *ALIAS.get(school, [])}
    # Mascot-independent matching: the canonical school name is usually a prefix
    # of ESPN's display name, while short-name aliases handle rebrands.
    return {norm(v) for v in vals if v}

def main() -> None:
    seed = json.loads(SEED.read_text(encoding='utf-8'))
    logo_map = json.loads(LOGOS.read_text(encoding='utf-8'))
    teams = logo_map.get('teams') or {}
    schools = seed.get('schools') or []
    by_school = {}
    for school in schools:
        aliases = aliases_for(school)
        matches = []
        for key, logo in teams.items():
            if '|' not in key or not logo:
                continue
            league, team_name = key.split('|', 1)
            if league == 'NCAA FB' or league == 'NCAA FCS' or league not in SPORT_PRIORITY:
                continue
            tnorm = norm(team_name)
            hit = False
            for alias in aliases:
                if tnorm == alias or tnorm.startswith(alias + ' ') or (' ' + alias + ' ') in (' ' + tnorm + ' '):
                    hit = True; break
            if hit:
                matches.append((league, team_name, logo))
        sports = defaultdict(list)
        for league, team_name, logo in matches:
            if team_name not in sports[league]:
                sports[league].append(team_name)
        logo = ''
        logo_source = None
        for league in SPORT_PRIORITY:
            if sports.get(league):
                logo = next((x[2] for x in matches if x[0] == league), '')
                if logo:
                    logo_source = league
                    break
        by_school[school] = {
            'school': school,
            'football': False,
            'aliases': sorted(aliases),
            'sportsFound': {k: sorted(v) for k, v in sorted(sports.items())},
            'logo': logo,
            'logoSourceSport': logo_source,
            'matchedTeamCount': len(matches),
        }
    unresolved = [s for s,v in by_school.items() if not v['logo']]
    result = {
        'schema': 1,
        'season': seed.get('season'),
        'definition': seed.get('definition'),
        'source': seed.get('source'),
        'expectedCount': seed.get('expectedCount'),
        'resolvedCount': len(by_school) - len(unresolved),
        'unresolvedCount': len(unresolved),
        'unresolvedSchools': unresolved,
        'schools': by_school,
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'expected': seed.get('expectedCount'), 'cataloged': len(by_school), 'resolved': result['resolvedCount'], 'unresolved': unresolved}, sort_keys=True))

if __name__ == '__main__':
    main()
