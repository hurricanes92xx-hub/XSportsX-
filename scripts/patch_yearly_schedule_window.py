#!/usr/bin/env python3
from pathlib import Path
import re

SERVICE = Path('app/src/main/java/com/xsportsx/app/SportsScheduleService.kt')
SCREEN = Path('app/src/main/java/com/xsportsx/app/SportsScheduleScreen.kt')

s = SERVICE.read_text(encoding='utf-8')

# Keep the schedule horizon finite and lightweight. This patch is deliberately
# idempotent because earlier schedule patches may already have rewritten load().
s = re.sub(r'(const\s+val\s+DAYS_AHEAD\s*=\s*)\d+L?', r'\g<1>30L', s, count=1)
if 'const val DAYS_AHEAD' not in s:
    s = s.replace('object SportsScheduleService {', 'object SportsScheduleService {\n    private const val DAYS_AHEAD = 30L', 1)

# The current service already has the newer window/fallback implementation.
# Do not try to replace that whole function (which caused CI failure when its
# shape changed). Instead, make its existing loader league-aware in-place.
if 'suspend fun load(leagueFilter:' not in s:
    old_sig = 'suspend fun load(): List<SportsEvent> = withContext(Dispatchers.IO) {'
    new_sig = 'suspend fun load(leagueFilter: String? = null): List<SportsEvent> = withContext(Dispatchers.IO) {'
    if old_sig not in s:
        raise SystemExit('schedule load signature not found: refusing unsafe rewrite')
    s = s.replace(old_sig, new_sig, 1)

    anchor = '        val today = LocalDate.now(ZoneId.systemDefault())\n'
    routing = '''        val today = LocalDate.now(ZoneId.systemDefault())
        val selected = leagueFilter?.trim().orEmpty()
        val canonical = if (selected.isBlank() || selected.equals("ALL", true)) "" else canonicalLeagueFor(selected)
        val targetLeagues = if (canonical.isBlank()) leagues else leagues.filter { it.league.equals(canonical, true) }
        if (targetLeagues.isEmpty()) return@withContext emptyList()
'''
    if anchor not in s:
        raise SystemExit('schedule load anchor not found: refusing unsafe rewrite')
    s = s.replace(anchor, routing, 1)
    s = s.replace('            leagues.map { league ->', '            targetLeagues.map { league ->', 1)

# Preserve exact display names for common soccer labels when upstream sends caps.
marker = '        "MONSTER JAM", "MONSTERJAM" -> "MONSTER JAM"\n'
if '"LALIGA" -> "LaLiga"' not in s and marker in s:
    s = s.replace(marker, marker + '        "LALIGA" -> "LaLiga"\n        "SERIE A" -> "Serie A"\n        "BUNDESLIGA" -> "Bundesliga"\n        "LIGUE 1" -> "Ligue 1"\n', 1)

SERVICE.write_text(s, encoding='utf-8')

t = SCREEN.read_text(encoding='utf-8')
# Selected league screens must request only that league, rather than loading
# every league and filtering after the network calls.
t = t.replace('SportsScheduleService.load()', 'SportsScheduleService.load(leagueFilter)', 1)
SCREEN.write_text(t, encoding='utf-8')

print('30-day schedule window and league-specific loading applied safely')
