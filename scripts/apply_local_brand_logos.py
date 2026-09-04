#!/usr/bin/env python3
"""Make the home sport/network cards use the bundled XSportsX logo renderer.

The old cards depended on remote logo URLs and silently rendered empty boxes when
those hosts failed. SportsLogos.kt already provides bundled SVGs plus a deterministic
XSportsX-styled vector fallback, so the UI must use that renderer for both Mobile and TV.
"""
from pathlib import Path

p = Path("app/src/main/java/com/xsportsx/app/FuturisticSports.kt")
s = p.read_text(encoding="utf-8")
old = s

s = s.replace(
    'LogoOnlyImage(sport.logoUrl,sport.name,Modifier.size(72.dp))',
    'XSportsLeagueLogo(sport.name, Modifier.size(72.dp), 72.dp)'
)
s = s.replace(
    'BadgeImage(network.logoUrl,network.name,Modifier.size(58.dp))',
    'XSportsNetworkLogo(network.name, Modifier.size(58.dp), 58.dp)'
)

if s == old:
    print("No logo-card patch needed; cards are already using the local renderer.")
else:
    p.write_text(s, encoding="utf-8")
    print("Patched Mobile/TV sport and network cards to use bundled XSportsX logos.")
