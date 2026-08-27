#!/usr/bin/env python3
from pathlib import Path
import re

SERVICE = Path('app/src/main/java/com/xsportsx/app/SportsScheduleService.kt')
SCREEN = Path('app/src/main/java/com/xsportsx/app/SportsScheduleScreen.kt')

s = SERVICE.read_text(encoding='utf-8')

# Keep the schedule horizon finite and lightweight. Match whitespace variants so
# CI patch ordering cannot make this step fail after another patch rewrites the file.
s = re.sub(r'(const\s+val\s+DAYS_AHEAD\s*=\s*)\d+L?', r'\g<1>30L', s, count=1)
if 'const val DAYS_AHEAD' not in s:
    s = s.replace('object SportsScheduleService {', 'object SportsScheduleService {\n    private const val DAYS_AHEAD = 30L', 1)

# Replace any existing load implementation with one stable implementation. This
# is deliberately tolerant of formatting/signature changes from earlier patches.
load_re = re.compile(r'(?ms)^\s*suspend\s+fun\s+load\s*\([^)]*\)\s*:\s*List<SportsEvent>\s*=\s*withContext\(Dispatchers\.IO\)\s*\{.*?^\s*\}\s*\n\s*private\s+suspend\s+fun\s+fetchLeagueWithFallbacks')
new_load = '''
    suspend fun load(leagueFilter: String? = null): List<SportsEvent> = withContext(Dispatchers.IO) {
        val today = LocalDate.now(ZoneId.systemDefault())
        val end = today.plusDays(DAYS_AHEAD)
        val dates = "${today.format(DateTimeFormatter.BASIC_ISO_DATE)}-${end.format(DateTimeFormatter.BASIC_ISO_DATE)}"
        val selected = leagueFilter?.trim().orEmpty()
        val canonical = if (selected.isBlank() || selected.equals("ALL", true)) "" else canonicalLeagueFor(selected)
        val targetLeagues = if (canonical.isBlank()) leagues else leagues.filter { it.league.equals(canonical, true) }
        if (targetLeagues.isEmpty()) return@withContext emptyList()

        val limiter = Semaphore(6)
        val results = coroutineScope {
            targetLeagues.map { league ->
                async {
                    runCatching {
                        withTimeout(7_000L) {
                            limiter.withPermit { fetchLeagueWithFallbacks(league, dates) }
                        }
                    }.getOrDefault(emptyList())
                }
            }.awaitAll()
        }

        results.flatten()
            .distinctBy { it.id.ifBlank { it.title + it.startUtc + it.league } }
            .filter { it.isLive || it.isPregame() || it.isUpcoming }
            .sortedWith(compareBy<SportsEvent> { !(it.isLive || it.isPregame()) }.thenBy { it.startUtc })
    }

    private suspend fun fetchLeagueWithFallbacks'''

match = load_re.search(s)
if not match:
    raise SystemExit('schedule load block not found: refusing to modify generated source')
s = s[:match.start()] + new_load + s[match.end():]

# Preserve exact display names for mixed-case soccer labels.
marker = '        "MONSTER JAM","MONSTERJAM" -> "MONSTER JAM"\n'
if '"LALIGA" -> "LaLiga"' not in s and marker in s:
    s = s.replace(marker, marker + '        "LALIGA" -> "LaLiga"\n        "SERIE A" -> "Serie A"\n        "BUNDESLIGA" -> "Bundesliga"\n        "LIGUE 1" -> "Ligue 1"\n', 1)

SERVICE.write_text(s, encoding='utf-8')

t = SCREEN.read_text(encoding='utf-8')
t = t.replace('SportsScheduleService.load()', 'SportsScheduleService.load(leagueFilter)', 1)
SCREEN.write_text(t, encoding='utf-8')

print('30-day schedule window, independent league loading, and pregame-safe filtering applied')
