#!/usr/bin/env python3
from pathlib import Path
import re

p = Path('app/src/main/java/com/xsportsx/app/FuturisticSports.kt')
s = p.read_text(encoding='utf-8')

# One renderer for all league/network cards. SportsLogos.kt owns the source
# hierarchy and aspect-ratio normalization, so cards no longer load arbitrary
# URLs directly from the UI data model.
s = s.replace(
    'BadgeImage(sport.logoUrl, sport.icon, Modifier.size(72.dp))',
    'XSportsLeagueLogo(sport.name, Modifier.size(72.dp), 72.dp)'
)
s = s.replace(
    'BadgeImage(network.logoUrl,network.name,Modifier.size(58.dp))',
    'XSportsNetworkLogo(network.name, Modifier.size(58.dp), 58.dp)'
)

# Clear legacy per-card remote logo URLs. The centralized logo resolver is now
# authoritative; keeping URLs here allowed bad aspect ratios and dead hosts to
# bypass the normalized renderer.
s = re.sub(r'XNetwork\(("[^"]+"),\s*("[^"]+"),\s*("[^"]+"),\s*"[^"]*"\)', r'XNetwork(\1, \2, \3)', s)
s = re.sub(r'SportVisual\(("[^"]+"),\s*("[^"]+"),\s*"[^"]*"\)', r'SportVisual(\1, \2, "")', s)

p.write_text(s, encoding='utf-8')
print('Unified league/network cards on XSportsLeagueLogo + XSportsNetworkLogo; removed legacy per-card remote logo URLs.')
