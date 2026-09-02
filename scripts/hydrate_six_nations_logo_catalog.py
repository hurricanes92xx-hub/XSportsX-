#!/usr/bin/env python3
"""Hydrate the six Men's Six Nations unions into the persistent logo cache."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'data/team_logo_map.json'
TEAMS={
 'England':'https://a.espncdn.com/i/teamlogos/countries/500/eng.png',
 'France':'https://a.espncdn.com/i/teamlogos/countries/500/fra.png',
 'Ireland':'https://a.espncdn.com/i/teamlogos/countries/500/irl.png',
 'Italy':'https://a.espncdn.com/i/teamlogos/countries/500/ita.png',
 'Scotland':'https://a.espncdn.com/i/teamlogos/countries/500/sco.png',
 'Wales':'https://a.espncdn.com/i/teamlogos/countries/500/wal.png',
}
ALIASES={'ENG':'England','England':'England','FRA':'France','France':'France','IRE':'Ireland','Ireland':'Ireland','ITA':'Italy','Italy':'Italy','SCO':'Scotland','Scotland':'Scotland','WAL':'Wales','Wales':'Wales'}
def norm(s): return ' '.join(str(s or '').upper().replace('-',' ').split())
def main():
 try: data=json.loads(CACHE.read_text(encoding='utf-8'))
 except Exception: data={'version':3,'teams':{}}
 if not isinstance(data,dict): data={'version':3,'teams':{}}
 teams=data.setdefault('teams',{})
 for name,url in TEAMS.items():
  teams[f'Six Nations|{norm(name)}']=url
  for alias,canonical in ALIASES.items():
   if canonical==name: teams[f'Six Nations|{norm(alias)}']=url
 CACHE.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 missing=[n for n in TEAMS if not teams.get(f'Six Nations|{norm(n)}')]
 print(f'Six Nations logo catalog: resolved={len(TEAMS)-len(missing)}/{len(TEAMS)}; missing={missing}')
 assert not missing
if __name__=='__main__': main()
