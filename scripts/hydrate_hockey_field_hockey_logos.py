#!/usr/bin/env python3
"""Merge dedicated NCAA hockey/field-hockey catalog logos into persistent cache."""
from __future__ import annotations
import json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'data'/'team_logo_map.json'
CATALOGS={
 "NCAA Women's Field Hockey": ROOT/'data'/'ncaa_field_hockey_team_catalog.json',
 "NCAA Men's Hockey": ROOT/'data'/'ncaa_mens_hockey_team_catalog.json',
 "NCAA Women's Hockey": ROOT/'data'/'ncaa_womens_hockey_team_catalog.json',
}
def norm(value):
    return re.sub(r'\s+',' ',re.sub(r'[^A-Z0-9]+',' ',str(value or '').upper())).strip()
def main():
    cache=json.loads(CACHE.read_text(encoding='utf-8')) if CACHE.exists() else {'version':3,'teams':{}}
    teams=cache.setdefault('teams',{})
    changed=0; aliases=0
    for league,path in CATALOGS.items():
        catalog=json.loads(path.read_text(encoding='utf-8'))
        for row in catalog.get('teams') or []:
            logo=str(row.get('logo') or '').strip()
            if not logo: continue
            names=[]
            for value in [row.get('displayName'), *(row.get('aliases') or [])]:
                if value and value not in names: names.append(value)
            for name in names:
                key=f'{league}|{norm(name)}'
                if teams.get(key)!=logo:
                    teams[key]=logo; changed+=1
                aliases+=1
    cache['version']=max(int(cache.get('version',3)),3)
    CACHE.write_text(json.dumps(cache,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'changed':changed,'aliasEntriesProcessed':aliases,'cacheEntries':len(teams)},sort_keys=True))
if __name__=='__main__': main()
