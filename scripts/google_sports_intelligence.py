#!/usr/bin/env python3
"""Build-time/background Google sports intelligence cache.

This intentionally never runs on the playback path. It records discovery metadata
only; XSportsX continues using its existing schedule/public-source resolver first.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path('data/google_sports_intelligence.json')
SPORTS = [
    ('NCAA FB','football','college football'), ('NCAA FCS','football','college football'),
    ('NCAA BB','basketball','college basketball'), ('NCAA WBB','basketball','women college basketball'),
    ('NCAA BASEBALL','baseball','college baseball'), ('NCAA SOFTBALL','softball','college softball'),
    ('NCAA MEN HOCKEY','hockey','college hockey'), ('NCAA WOMEN HOCKEY','hockey','women college hockey'),
    ('NCAA VB','volleyball','college volleyball'), ('NCAA MEN SOCCER','soccer','college soccer'),
    ('NCAA WOMEN SOCCER','soccer','women college soccer'), ('NCAA MEN LAX','lacrosse','college lacrosse'),
    ('NCAA WOMEN LAX','lacrosse','women college lacrosse'), ('NCAA WRESTLING','wrestling','college wrestling'),
    ('NFL','football','NFL'), ('NBA','basketball','NBA'), ('WNBA','basketball','WNBA'), ('MLB','baseball','MLB'),
    ('NHL','hockey','NHL'), ('MLS','soccer','MLS'), ('EPL','soccer','Premier League'), ('UCL','soccer','Champions League'),
    ('LaLiga','soccer','La Liga'), ('Serie A','soccer','Serie A'), ('Bundesliga','soccer','Bundesliga'),
    ('Ligue 1','soccer','Ligue 1'), ('UFC','mma','UFC'), ('BOXING','boxing','boxing'),
    ('F1','racing','Formula 1'), ('NASCAR','racing','NASCAR'), ('INDYCAR','racing','IndyCar')
]

def main():
    # This manifest is intentionally metadata-only. A backend job may enrich it from
    # Google/YouTube official/public results; the APK never queries Google to play a stream.
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'schema': 1,
        'generatedAt': datetime.now(timezone.utc).isoformat(),
        'ttlMinutes': 60,
        'source': 'google-search-youtube-discovery',
        'playbackBlocking': False,
        'leagues': [
            {'league': n, 'sport': s, 'query': q, 'officialOnly': True}
            for n, s, q in SPORTS
        ]
    }
    OUT.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    print(f'wrote {len(SPORTS)} Google sports discovery profiles')

if __name__ == '__main__': main()
