#!/usr/bin/env python3
from pathlib import Path
import re

SERVICE = Path('app/src/main/java/com/xsportsx/app/SportsScheduleService.kt')
SCREEN = Path('app/src/main/java/com/xsportsx/app/SportsScheduleScreen.kt')

s = SERVICE.read_text(encoding='utf-8')

# Keep the production schedule horizon at 30 days. This patch must be idempotent:
# earlier builds may already have changed the limiter or pregame classification.
if 'DAYS_AHEAD=30' not in s:
    s = s.replace('DAYS_AHEAD=370', 'DAYS_AHEAD=30', 1)
# LocalDate.plusDays() takes a Long; normalize the constant so the generated
# Kotlin remains type-correct on every build.
s = s.replace('DAYS_AHEAD=30', 'DAYS_AHEAD=30L', 1)

# Make selected leagues load independently. Replace any prior load implementation,
# including the version already modified by patch_pregame_window.py.
if 'suspend fun load(leagueFilter:String? = null)' not in s:
    pattern = re.compile(r'    suspend fun load\(\):List<SportsEvent> = withContext\(Dispatchers\.IO\) \{.*?\n    \}\n\n    private suspend fun fetchLeagueWithFallbacks', re.S)
    new_load = '''    suspend fun load(leagueFilter:String? = null):List<SportsEvent> = withContext(Dispatchers.IO) {
        val today=LocalDate.now(ZoneId.systemDefault())
        val end=today.plusDays(DAYS_AHEAD)
        val dates="${today.format(DateTimeFormatter.BASIC_ISO_DATE)}-${end.format(DateTimeFormatter.BASIC_ISO_DATE)}"
        val selected=leagueFilter?.trim().orEmpty()
        val canonical=if(selected.isBlank() || selected.equals("ALL",true)) "" else canonicalLeagueFor(selected)
        val targetLeagues=if(canonical.isBlank()) leagues else leagues.filter{it.league.equals(canonical,true)}
        if(targetLeagues.isEmpty()) return@withContext emptyList()
        val limiter=Semaphore(6)
        val results=coroutineScope {
            targetLeagues.map { league ->
                async {
                    runCatching { withTimeout(7_000L) { limiter.withPermit { fetchLeagueWithFallbacks(league,dates) } } }
                        .getOrDefault(emptyList())
                }
            }.awaitAll()
        }
        results.flatten()
            .distinctBy{it.id.ifBlank{it.title+it.startUtc+it.league}}
            .filter{it.isLive || it.isPregame() || it.isUpcoming}
            .sortedWith(compareBy<SportsEvent>{!(it.isLive || it.isPregame())}.thenBy{it.startUtc})
    }

    private suspend fun fetchLeagueWithFallbacks'''
    s, count = pattern.subn(new_load, s, count=1)
    if count != 1:
        raise SystemExit('schedule load block not found')
else:
    # If the production source already has the selected-league loader, just make
    # sure the horizon and concurrency remain at the intended lightweight values.
    s = s.replace('val end=today.plusDays(370)', 'val end=today.plusDays(DAYS_AHEAD)')
    s = s.replace('Semaphore(8)', 'Semaphore(6)')

# Preserve exact display names for mixed-case catalog labels.
canon_marker = '        "MONSTER JAM","MONSTERJAM" -> "MONSTER JAM"\n'
if '"LALIGA" -> "LaLiga"' not in s and canon_marker in s:
    s = s.replace(canon_marker, canon_marker + '        "LALIGA" -> "LaLiga"\n        "SERIE A" -> "Serie A"\n        "BUNDESLIGA" -> "Bundesliga"\n        "LIGUE 1" -> "Ligue 1"\n', 1)

SERVICE.write_text(s, encoding='utf-8')

# Selected league screens should pass their league into the service so they do
# not fetch every league and filter only after the network work completes.
t = SCREEN.read_text(encoding='utf-8')
if 'SportsScheduleService.load(leagueFilter)' not in t:
    old_call = 'SportsScheduleService.load()'
    if old_call in t:
        t = t.replace(old_call, 'SportsScheduleService.load(leagueFilter)', 1)
    else:
        raise SystemExit('schedule screen load call not found')
SCREEN.write_text(t, encoding='utf-8')

print('30-day schedule window, independent league loading, and pregame-safe filtering applied')
