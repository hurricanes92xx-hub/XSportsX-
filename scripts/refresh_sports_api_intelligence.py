#!/usr/bin/env python3
"""Generate policy for background sports-API/schedule corroboration.

Actual retrieval belongs to the backend refresh worker; playback/UI consumes only cached data.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path('data/sports_api_refresh.json')
LEAGUES = [
 'NFL','NCAA FB','NCAA FCS','NBA','WNBA','NCAA BB','NCAA WBB','MLB','NHL',
 'NCAA BASEBALL','NCAA SOFTBALL','NCAA MEN HOCKEY','NCAA WOMEN HOCKEY','NCAA VB',
 'NCAA MEN SOCCER','NCAA WOMEN SOCCER','NCAA MEN LAX','NCAA WOMEN LAX','NCAA WRESTLING',
 'MLS','EPL','UCL','LaLiga','Serie A','Bundesliga','Ligue 1','UFC','BOXING','F1','NASCAR','INDYCAR',
 'MONSTER JAM','WWE','TNA','AEW','PWHL'
]

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'schema': 2,
        'generatedAt': datetime.now(timezone.utc).isoformat(),
        'playbackBlocking': False,
        'refreshMinutes': 30,
        'leagues': LEAGUES,
        'providers': ['ESPN', 'TheSportsDB'],
        'scheduleSources': ['official conference/team schedules','official promotion/event schedules','official Monster Jam schedule'],
        'fallbackOrder': ['existing schedule', 'ESPN', 'TheSportsDB', 'official event schedule', 'EPG', 'Google', 'Telegram'],
        'rule': 'Use cached corroboration only; never call an external metadata API from the Play path.'
    }
    OUT.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    print(f'wrote sports intelligence refresh policy for {len(LEAGUES)} catalog leagues/events')

if __name__ == '__main__':
    main()
