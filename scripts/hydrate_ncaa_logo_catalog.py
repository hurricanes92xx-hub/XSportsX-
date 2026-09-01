#!/usr/bin/env python3
"""Hydrate the persistent NCAA logo catalog from ESPN plus fixed small-school entries."""
from __future__ import annotations
import json,re,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'data'/'team_logo_map.json'
HEADERS={'User-Agent':'XSportsX-LogoCatalog/1.2','Accept':'application/json'}
SOURCES={
 'NCAA FB':'https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams?limit=1000',
 'NCAA FCS':'https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams?limit=1000',
 'NCAA BB':'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams?limit=1000',
 'NCAA WBB':'https://site.api.espn.com/apis/site/v2/sports/basketball/womens-college-basketball/teams?limit=1000',
}
# Deterministic catalog entries for football schools that are outside ESPN's current
# college-football team endpoint but still appear in the FCS schedule.
FIXED={
 'NCAA FCS':{
  'Webber International Warriors':'https://a.espncdn.com/i/teamlogos/ncaa/500/2691.png',
  'Thomas More College Saints':'https://a.espncdn.com/i/teamlogos/ncaa/500/2646.png',
  'Point University Skyhawks':'https://a.espncdn.com/i/teamlogos/ncaa/500/3179.png',
  'Rio Grande Red Storm':'https://commons.wikimedia.org/wiki/Special:Redirect/file/Rio_grande_redstorm_wmark.png',
  'UFTL Eagles':'https://uftlathletics.com/images/logos/site/site.png',
 }
}
def norm(s): return re.sub(r'\s+',' ',re.sub(r'[^A-Z0-9]+',' ',str(s or '').upper())).strip()
def get(url):
 req=urllib.request.Request(url,headers=HEADERS)
 with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read().decode('utf-8','ignore'))
def extract(root):
 rows=[]
 groups=[]
 if isinstance(root,dict) and root.get('sports'):
  for sport in root.get('sports') or []:
   for league in sport.get('leagues') or []: groups.extend(league.get('teams') or [])
 if not groups and isinstance(root,dict): groups=root.get('teams') or []
 for item in groups:
  t=item.get('team') if isinstance(item,dict) else item
  if not isinstance(t,dict): continue
  logos=t.get('logos') or []
  logo=str(logos[0].get('href') or '').strip() if logos and isinstance(logos[0],dict) else ''
  names={t.get('displayName'),t.get('shortDisplayName'),t.get('name'),t.get('abbreviation'),t.get('slug')}
  for name in names:
   if name and logo: rows.append((str(name).strip(),logo))
 return rows
def main():
 p=json.loads(CACHE.read_text(encoding='utf-8')) if CACHE.exists() else {'version':3,'teams':{},'sources':{}}
 p.setdefault('teams',{});p.setdefault('sources',{});report={}
 for league,url in SOURCES.items():
  rows=extract(get(url))
  if not rows: raise RuntimeError(f'No teams returned for {league}')
  for name,logo in rows:p['teams'][f'{league}|{norm(name)}']=logo
  p['sources'][league]={'provider':'ESPN official team catalog','teams':len(rows),'url':url,'completeCatalog':True}
  report[league]=len(rows)
 for league,entries in FIXED.items():
  for name,logo in entries.items(): p['teams'][f'{league}|{norm(name)}']=logo
  p['sources'].setdefault(league,{})['fixedSmallSchoolEntries']=len(entries)
 p['generatedAt']=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
 CACHE.write_text(json.dumps(p,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
 print('NCAA logo catalog hydrated:',json.dumps({**report,'fixed_small_school_entries':sum(len(v) for v in FIXED.values())},sort_keys=True))
if __name__=='__main__':main()
