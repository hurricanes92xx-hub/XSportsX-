#!/usr/bin/env python3
from pathlib import Path
import re

SERVICE = Path('app/src/main/java/com/xsportsx/app/SportsScheduleService.kt')
SCREEN = Path('app/src/main/java/com/xsportsx/app/SportsScheduleScreen.kt')

s = SERVICE.read_text(encoding='utf-8')
s, n_days = re.subn(r'(private const val DAYS_AHEAD\s*=\s*)\d+(?:L)?', r'\g<1>7', s, count=1)
if n_days != 1:
    raise SystemExit('Could not set the interactive schedule window to 7 days')
s, n_cap = re.subn(r'(private const val MAX_GAMES_PER_LEAGUE\s*=\s*)\d+', r'\g<1>75', s, count=1)
if n_cap != 1:
    raise SystemExit('Could not set per-league schedule cap to 75')
SERVICE.write_text(s, encoding='utf-8')

t = SCREEN.read_text(encoding='utf-8')
old = '    val visible = if (leagueFilter == "ALL") statusVisible else statusVisible.filter { it.league.equals(leagueFilter, true) }'
new = '''    val visible = run {
        val cutoff = java.time.Instant.now().plus(java.time.Duration.ofDays(7))
        val windowed = statusVisible.filter { event ->
            runCatching { java.time.Instant.parse(event.startUtc).isBefore(cutoff) }.getOrDefault(true)
        }
        if (leagueFilter == "ALL") windowed else windowed.filter { it.league.equals(leagueFilter, true) }
    }'''
if old not in t:
    raise SystemExit('Schedule screen visibility anchor not found')
t = t.replace(old, new, 1)
SCREEN.write_text(t, encoding='utf-8')

print('Interactive schedule limited to 7 days; per-league load capped at 75; live/pregame events remain prioritized.')
