from pathlib import Path
import re

p = Path("app/src/main/java/com/xsportsx/app/TvHome.kt")
if not p.is_file():
    raise SystemExit(f"Missing TV source: {p}")

s = p.read_text(encoding="utf-8")

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

s = s.replace(
    'var tvModeEnabled by remember{mutableStateOf(false)};',
    ''
)
s = s.replace(
    'TvTopBar(onSettings={selectedNav="SETTINGS"},tvModeEnabled=tvModeEnabled,onToggleTvMode={tvModeEnabled=!tvModeEnabled})',
    'TvTopBar{selectedNav="SETTINGS"}'
)

# The ticker must remain inside TvHome's Box scope so Modifier.align() resolves
# against BoxScope. The previous compacted source closed Box one brace too early.
# Normalize only this exact malformed boundary and keep the patch idempotent.
old_boundary = '}}}}};HomeSportsTicker(Modifier.align(Alignment.BottomCenter).fillMaxWidth())}}'
new_boundary = '}}}};HomeSportsTicker(Modifier.align(Alignment.BottomCenter).fillMaxWidth())}}'
if old_boundary in s:
    s = s.replace(old_boundary, new_boundary, 1)
    fixed = True

if len(re.findall(r'@Composable\s+private fun TvActionButton\s*\(', s)) > 1:
    raise SystemExit("Duplicate TvActionButton definitions detected; refusing to patch")

p.write_text(s, encoding="utf-8")
print("TV navigation patch applied safely" if fixed else "TV navigation source already clean")
