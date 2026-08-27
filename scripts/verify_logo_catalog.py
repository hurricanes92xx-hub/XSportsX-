from pathlib import Path

source = Path('app/src/main/java/com/xsportsx/app/SportsLogos.kt').read_text()

leagues = [
    'NFL','NBA','NCAA FB','NCAA BB','NCAA VB','MLB','NHL','UFC','BOXING','RUGBY',
    'VOLLEYBALL','LACROSSE','WRESTLING','FORMULA 1','NASCAR','DTM','MOTOGP','WRC',
    'WEC','FORMULA E','MXGP','MONSTER JAM','SOCCER','MLS','EPL','WNBA'
]
networks = [
    'ESPN','ESPN2','ESPNU','ESPN+','NFL NETWORK','FS1','CBS SPORTS','SEC NETWORK',
    'ACC NETWORK','BIG TEN NETWORK','ESPN+','PAC-12 NETWORK','NBA TV','MLB NETWORK',
    'NHL NETWORK','UFC FIGHT PASS','RED BULL TV','MONSTER JAM','RUGBYPASS TV'
]

for key in sorted(set(leagues + networks)):
    if f'"{key}"' not in source:
        raise SystemExit(f'Missing explicit logo mapping: {key}')

required_assets = ['nfl.svg','nba.svg','ncaa.svg','mlb.svg','nhl.svg','ufc.svg','espn.svg','cbs.svg','premierleague.svg']
for asset in required_assets:
    path = Path('app/src/main/assets/brand_logos') / asset
    if not path.is_file() or path.stat().st_size < 50:
        raise SystemExit(f'Missing bundled logo asset: {path}')

if 'a.espncdn.com/i/teamlogos/leagues' in source:
    raise SystemExit('SportsLogos must not depend on ESPN CDN league logos')

print(f'Logo catalog OK: {len(set(leagues))} leagues, {len(set(networks))} networks, {len(required_assets)} bundled assets')
