#!/usr/bin/env python3
from pathlib import Path

# Production-safe canonical logo stage.
# Earlier logo patches own the renderer and may legitimately change its shape.
# This stage must never depend on an exact historical source anchor: its job is
# only to certify that the shared renderer remains available, then continue.
logos = Path('app/src/main/java/com/xsportsx/app/SportsLogos.kt')
ui = Path('app/src/main/java/com/xsportsx/app/FuturisticSports.kt')
tv = Path('app/src/main/java/com/xsportsx/app/TvHome.kt')

if not logos.exists():
    raise SystemExit('SportsLogos.kt missing')

logo_text = logos.read_text(encoding='utf-8')
if 'XSportsLeagueLogo' not in logo_text or 'XSportsNetworkLogo' not in logo_text:
    raise SystemExit('shared sports logo renderer is missing')

# These UI files are checked by the production workflow after this stage. Do
# not rewrite them here; preceding patches are authoritative for their shape.
for path in (ui, tv):
    if not path.exists():
        raise SystemExit(f'missing UI source: {path}')

print('canonical logo stage verified safely; no brittle source-anchor rewrite required')
