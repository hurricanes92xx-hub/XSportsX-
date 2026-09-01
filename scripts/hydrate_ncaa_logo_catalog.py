#!/usr/bin/env python3
"""Hydrate persistent NCAA team-logo catalogs from ESPN plus deterministic aliases."""
from __future__ import annotations
import json,re,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'data'/'team_logo_map.json'
HEADERS={'User-Agent':'XSportsX-LogoCatalog/1.4','Accept':'application/json'}

# Keep one persistent catalog for every college team sport represented by the
# schedule feed.  ESPN is the authoritative source; failed endpoints are
# recorded so one unavailable sport cannot block the entire refresh.
SOURCES={
 'NCAA FB':'https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams?limit=1000',
 'NCAA FCS':'https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams?limit=1000',
 'NCAA BB':'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams?limit=1000',
 'NCAA WBB':'https://site.api.espn.com/apis/site/v2/sports/basketball/womens-college-basketball/teams?limit=1000',
 "NCAA Women's Volleyball":'https://site.api.espn.com/apis/site/v2/sports/volleyball/womens-college-volleyball/teams?limit=1000',
 "NCAA Men's Volleyball":'https://site.api.espn.com/apis/site/v2/sports/volleyball/mens-college-volleyball/teams?limit=1000',
 "NCAA Men's Hockey":'https://site.api.espn.com/apis/site/v2/sports/hockey/mens-college-hockey/teams?limit=1000',
 "NCAA Women's Hockey":'https://site.api.espn.com/apis/site/v2/sports/hockey/womens-college-hockey/teams?limit=1000',
 "NCAA Women's Field Hockey":'https://site.api.espn.com/apis/site/v2/sports/field-hockey/womens-college-field-hockey/teams?limit=1000',
 "NCAA Men's Soccer":'https://site.api.espn.com/apis/site/v2/sports/soccer/usa.ncaa.men/teams?limit=1000',
 "NCAA Women's Soccer":'https://site.api.espn.com/apis/site/v2/sports/soccer/usa.ncaa.women/teams?limit=1000',
 "NCAA Men's Lacrosse":'https://site.api.espn.com/apis/site/v2/sports/lacrosse/mens-college-lacrosse/teams?limit=1000',
 "NCAA Women's Lacrosse":'https://site.api.espn.com/apis/site/v2/sports/lacrosse/womens-college-lacrosse/teams?limit=1000',
 "NCAA Baseball":'https://site.api.espn.com/apis/site/v2/sports/baseball/college-baseball/teams?limit=1000',
 "NCAA Softball":'https://site.api.espn.com/apis/site/v2/sports/softball/college-softball/teams?limit=1000',
 "NCAA Men's Tennis":'https://site.api.espn.com/apis/site/v2/sports/tennis/atp/teams?limit=1000',
 "NCAA Women's Tennis":'https://site.api.espn.com/apis/site/v2/sports/tennis/wta/teams?limit=1000',
 "NCAA Men's Golf":'https://site.api.espn.com/apis/site/v2/sports/golf/pga/teams?limit=1000',
 "NCAA Women's Golf":'https://site.api.espn.com/apis/site/v2/sports/golf/lpga/teams?limit=1000',
 'NCAA Wrestling':'https://site.api.espn.com/apis/site/v2/sports/wrestling/college-wrestling/teams?limit=1000',
 'NCAA Gymnastics':'https://site.api.espn.com/apis/site/v2/sports/gymnastics/college-gymnastics/teams?limit=1000',
 'NCAA Swimming & Diving':'https://site.api.espn.com/apis/site/v2/sports/swimming/college-swimming/teams?limit=1000',
 'NCAA Track & Field':'https://site.api.espn.com/apis/site/v2/sports/track-and-field/college-track-and-field/teams?limit=1000',
}
UTRGV_LOGO='https://a.espncdn.com/i/teamlogos/ncaa/500/292.png'
UTRGV_ALIASES={'UT Rio Grande':'UT Rio Grande','UT Rio Grande Valley Vaqueros':'UT Rio Grande Valley Vaqueros','UTRGV':'UTRGV','UT Rio Grande Valley':'UT Rio Grande Valley'}
FIXED={
 'NCAA FB':UTRGV_ALIASES,
 'NCAA FCS':{
  'Webber International Warriors':'https://a.espncdn.com/i/teamlogos/ncaa/500/2691.png',
  'Thomas More College Saints':'https://a.espncdn.com/i/teamlogos/ncaa/500/2646.png',
  'Point University Skyhawks':'https://a.espncdn.com/i/teamlogos/ncaa/500/3179.png',
  'Rio Grande Red Storm':'https://commons.wikimedia.org/wiki/Special:Redirect/file/Rio_grande_redstorm_wmark.png',
  'UFTL Eagles':'https://uftlathletics.com/images/logos/site/site.png',
  **UTRGV_ALIASES,
 }
}
def norm(s): return re.sub(r'\s+',' ',re.sub(r'[^A-Z0-9]+',' ',str(s or '').upper())).strip()
def get(url):
 req=urllib.request.Request(url,headers=HEADERS)
 with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read().decode('utf-8','ignore'))
def extract(root):
 rows=[];groups=[]
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
 p=json.loads(CACHE.read_text(encoding='utf-8')) if CACHE.exists() else {'version':4,'teams':{},'sources':{}}
 p.setdefault('teams',{});p.setdefault('sources',{});report={};failures={}
 for league,url in SOURCES.items():
  try: rows=extract(get(url))
  except Exception as exc: failures[league]=str(exc);continue
  if not rows: failures[league]='No teams returned';continue
  for name,logo in rows:p['teams'][f'{league}|{norm(name)}']=logo
  p['sources'][league]={'provider':'ESPN official team catalog','teams':len(rows),'url':url,'completeCatalog':True}
  report[league]=len(rows)
 for league,entries in FIXED.items():
  for name,logo in entries.items():
   if league=='NCAA FB': logo=UTRGV_LOGO
   elif league=='NCAA FCS' and name in UTRGV_ALIASES: logo=UTRGV_LOGO
   p['teams'][f'{league}|{norm(name)}']=logo
  p['sources'].setdefault(league,{})['fixedSmallSchoolEntries']=len(entries)
 p['generatedAt']=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
 CACHE.write_text(json.dumps(p,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
 print('NCAA logo catalog hydrated:',json.dumps({'catalogs':report,'failures':failures,'fixed_small_school_entries':sum(len(v) for v in FIXED.values())},sort_keys=True))
if __name__=='__main__':main()
