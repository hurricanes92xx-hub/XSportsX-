#!/usr/bin/env python3
from pathlib import Path
required = [Path('app/src/main/java/com/xsportsx/app/SportsLogos.kt'), Path('app/src/main/java/com/xsportsx/app/FuturisticSports.kt'), Path('app/src/main/java/com/xsportsx/app/TvHome.kt')]
for path in required:
    if not path.exists():
        raise SystemExit(f'missing required source: {path}')
logo_text = required[0].read_text(encoding='utf-8')
if 'XSportsLeagueLogo' not in logo_text or 'XSportsNetworkLogo' not in logo_text:
    raise SystemExit('shared sports logo renderer is missing')
print('canonical logo stage verified; no source rewrite performed')
