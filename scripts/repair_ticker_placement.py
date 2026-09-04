#!/usr/bin/env python3
from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'app/src/main/java/com/xsportsx/app/FuturisticSports.kt'
s = p.read_text(encoding='utf-8')
old = '''                    MobileBottomNav(selectedSection){section->if(section=="SOURCE")onSource()else selectedSection=section}\n'''
new = '''                    HomeSportsTicker(Modifier.padding(bottom = 4.dp))\n                    MobileBottomNav(selectedSection){section->if(section=="SOURCE")onSource()else selectedSection=section}\n'''
if old not in s:
    raise SystemExit('mobile bottom nav placement not found')
if 'HomeSportsTicker(Modifier.padding(bottom = 4.dp))' not in s:
    s = s.replace(old, new, 1)
    p.write_text(s, encoding='utf-8')
    print('TICKER_PLACEMENT: changed')
else:
    print('TICKER_PLACEMENT: already-compliant')
