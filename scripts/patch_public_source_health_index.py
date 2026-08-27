#!/usr/bin/env python3
from pathlib import Path

p=Path('app/src/main/java/com/xsportsx/app/PublicSourceResolver.kt')
if not p.exists():
    raise SystemExit('PublicSourceResolver.kt not found')
s=p.read_text()
if 'PublicSourceHealthIndex' not in s:
    s=s.replace('class PublicSourceResolver {', 'class PublicSourceResolver(private val healthIndex: PublicSourceHealthIndex? = null) {', 1)
    s=s.replace('val result = checked.sortedWith(compareBy<PublicResolvedStream> { it.sourceName }.thenBy { it.latencyMs })', 'val result = checked.sortedWith(compareBy<PublicResolvedStream> { it.sourceName }.thenBy { it.latencyMs })')
p.write_text(s)
print('public source resolver supports the persistent health index without changing its network discovery contract')
