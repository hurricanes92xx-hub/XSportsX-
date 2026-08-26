from pathlib import Path
import re

p = Path("app/src/main/java/com/xsportsx/app/TvHome.kt")
if not p.is_file():
    raise SystemExit(f"Missing TV source: {p}")

s = p.read_text(encoding="utf-8")

# TvHome.kt is intentionally compacted. Keep this patch minimal and idempotent:
# the previous version rewrote TvTopBar and accidentally created duplicate
# composables, which broke Kotlin compilation. The base TV navigation is already
# valid, so only normalize the malformed generic return syntax introduced by the
# earlier patch chain.
patterns = [
    (r'private suspend fun loadTvGames\(liveOnly:Boolean=true\):List<TvGame>=',
     'private suspend fun loadTvGames(liveOnly:Boolean=true): List<TvGame> ='),
    (r'private suspend fun loadTvGames\(liveOnly: Boolean = true\): List<TvGame>\s*=',
     'private suspend fun loadTvGames(liveOnly: Boolean = true): List<TvGame> ='),
]

fixed = False
for pattern, replacement in patterns:
    s, n = re.subn(pattern, replacement, s, count=1)
    fixed = fixed or n > 0

# Remove only legacy TV-mode state/call additions if they were left in a source
# produced by an older patch. Never touch the existing TvActionButton definition.
s = s.replace(
    'var tvModeEnabled by remember{mutableStateOf(false)};',
    ''
)
s = s.replace(
    'TvTopBar(onSettings={selectedNav="SETTINGS"},tvModeEnabled=tvModeEnabled,onToggleTvMode={tvModeEnabled=!tvModeEnabled})',
    'TvTopBar{selectedNav="SETTINGS"}'
)

# The base source should contain exactly one TvActionButton. If an older patch
# somehow duplicated it, fail loudly rather than producing another bad build.
if len(re.findall(r'@Composable\s+private fun TvActionButton\s*\(', s)) > 1:
    raise SystemExit("Duplicate TvActionButton definitions detected; refusing to patch")

p.write_text(s, encoding="utf-8")
print("TV navigation patch applied safely" if fixed else "TV navigation source already clean")
