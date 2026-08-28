#!/usr/bin/env python3
from pathlib import Path
import re

SERVICE = Path('app/src/main/java/com/xsportsx/app/SportsScheduleService.kt')
s = SERVICE.read_text(encoding='utf-8')

MARKER = 'TSDB_LONG_TAIL_BACKUP_V1'
if MARKER in s:
    print('Schedule backup sources already present')
    raise SystemExit(0)

MODEL = '''private data class TsdbFallbackLeague(
    val canonicalLeague: String,
    val leagueId: Int,
    val officialUrl: String
)

private data class TsdbFallbackCache(
    val loadedAtMs: Long,
    val events: List<SportsEvent>
)

'''
model_anchor = 'private data class ScheduleWindow(val start: LocalDate, val end: LocalDate) {'
if 'private data class TsdbFallbackLeague' not in s:
    if model_anchor not in s:
        raise SystemExit('schedule window model anchor not found')
    s = s.replace(model_anchor, MODEL + model_anchor, 1)

CONSTANTS = '''    // TSDB_LONG_TAIL_BACKUP_V1
    // Last-resort only; primary ESPN/official feeds remain authoritative.
    private const val TSDB_API_BASE = "https://www.thesportsdb.com/api/v1/json/123"
    private const val TSDB_CACHE_MS = 15L * 60L * 1000L
    private const val TSDB_BACKUP_TIMEOUT_MS = 2_500L
    private val tsdbFallbackCache = java.util.concurrent.ConcurrentHashMap<String, TsdbFallbackCache>()
    private val tsdbFallbackLeagues = listOf(
        TsdbFallbackLeague("F1", 4370, "https://www.formula1.com/"),
        TsdbFallbackLeague("FORMULA E", 4371, "https://www.fiaformulae.com/"),
        TsdbFallbackLeague("INDYCAR", 4373, "https://www.indycar.com/"),
        TsdbFallbackLeague("MOTOGP", 4407, "https://www.motogp.com/"),
        TsdbFallbackLeague("WRC", 4409, "https://www.fia.com/events/world-rally-championship/season-2026/events-calendar"),
        TsdbFallbackLeague("WEC", 4413, "https://www.fiawec.com/"),
        TsdbFallbackLeague("IMSA", 4488, "https://www.imsa.com/"),
        TsdbFallbackLeague("NASCAR", 4393, "https://www.nascar.com/"),
        TsdbFallbackLeague("MXGP", 4587, "https://www.mxgp.com/calendar"),
        TsdbFallbackLeague("UFC", 4443, "https://www.ufc.com/watch/schedule"),
        TsdbFallbackLeague("BOXING", 4445, "https://www.espn.com/boxing/"),
        TsdbFallbackLeague("WRESTLING", 4444, "https://www.wwe.com/"),
        TsdbFallbackLeague("WRESTLING_ROH", 4448, "https://www.allelitewrestling.com/"),
        TsdbFallbackLeague("WRESTLING_NJPW", 4449, "https://www.njpw.co.jp/event-calendar"),
        TsdbFallbackLeague("WRESTLING_TNA", 4455, "https://tnawrestling.com/events/")
    )
'''
constants_anchor = '    private const val CONNECT_TIMEOUT_MS = 1_800\n'
if 'private const val TSDB_API_BASE' not in s:
    if constants_anchor not in s:
        raise SystemExit('schedule timeout constants anchor not found')
    s = s.replace(constants_anchor, constants_anchor + CONSTANTS, 1)

LEAGUES = '''    private val TSDB_LONG_TAIL_LEAGUES = setOf(
        "F1", "FORMULA E", "INDYCAR", "MOTOGP", "WRC", "WEC", "IMSA", "NASCAR", "MXGP",
        "UFC", "BOXING", "WRESTLING"
    )

'''
if 'TSDB_LONG_TAIL_LEAGUES' not in s:
    anchor = '    val uiLeagueChoices: List<String> = listOf(\n'
    if anchor not in s:
        raise SystemExit('league choices anchor not found')
    s = s.replace(anchor, LEAGUES + anchor, 1)

# Include long-tail events in the top-level filter without depending on one
# exact result-pipeline shape from earlier schedule patches.
old_filter = 'leagues.any { it.league == normalizeLeague(event.league) } && (event.isLive || event.isPregame() || event.isUpcoming)'
new_filter = '(leagues.any { it.league == normalizeLeague(event.league) } || TSDB_LONG_TAIL_LEAGUES.contains(normalizeLeague(event.league))) && (event.isLive || event.isPregame() || event.isUpcoming)'
if old_filter in s and 'TSDB_LONG_TAIL_LEAGUES.contains(normalizeLeague(event.league))' not in s:
    s = s.replace(old_filter, new_filter, 1)

if 'fetchTheSportsDbLongTailFallbacks()' not in s:
    merge_patterns = [
        r'\n(?P<indent>\s*)results\.flatten\(\)',
        r'\n(?P<indent>\s*)\(results\.flatten\(\) \+ fetchSpecialScheduleFeed\(\)\)'
    ]
    merged = False
    for pattern in merge_patterns:
        m = re.search(pattern, s)
        if m:
            indent = m.group('indent')
            replacement = f'\n{indent}(results.flatten() + fetchTheSportsDbLongTailFallbacks())'
            s = s[:m.start()] + replacement + s[m.end():]
            merged = True
            break
    if not merged:
        raise SystemExit('schedule result merge anchor not found')

IMPLEMENTATION = r'''    private suspend fun fetchTheSportsDbLongTailFallbacks(): List<SportsEvent> = coroutineScope {
        tsdbFallbackLeagues.map { fallback ->
            async {
                withTimeoutOrNull(TSDB_BACKUP_TIMEOUT_MS) {
                    runCatching { fetchTheSportsDbFallback(fallback) }.getOrDefault(emptyList())
                }.orEmpty()
            }
        }.awaitAll().flatten().distinctBy { event ->
            listOf(normalizeLeague(event.league), normalize(event.home), normalize(event.away), event.startUtc.take(16)).joinToString("|")
        }
    }

    private fun fetchTheSportsDbFallback(fallback: TsdbFallbackLeague): List<SportsEvent> {
        val now = System.currentTimeMillis()
        val cached = tsdbFallbackCache[fallback.canonicalLeague]
        if (cached != null && now - cached.loadedAtMs < TSDB_CACHE_MS) return cached.events
        val root = JSONObject(http("$TSDB_API_BASE/eventsnextleague.php?id=${fallback.leagueId}"))
        val events = root.optJSONArray("events") ?: return emptyList()
        val out = ArrayList<SportsEvent>(events.length())
        for (i in 0 until events.length()) {
            val event = events.optJSONObject(i) ?: continue
            val date = event.optString("dateEvent").trim()
            if (date.isBlank()) continue
            val time = event.optString("strTime").trim().ifBlank { "00:00:00" }
            val start = event.optString("strTimestamp").trim().ifBlank { "${date}T${time}Z" }
            val canonical = if (fallback.canonicalLeague.startsWith("WRESTLING")) "WRESTLING" else fallback.canonicalLeague
            val title = event.optString("strEvent").ifBlank { canonical }
            val home = event.optString("strHomeTeam").ifBlank { title }
            val away = event.optString("strAwayTeam").ifBlank { canonical }
            out += SportsEvent(
                "tsdb-${fallback.leagueId}-${event.optString("idEvent").ifBlank { i.toString() }}",
                if (canonical in setOf("F1", "FORMULA E", "INDYCAR", "MOTOGP", "WRC", "WEC", "IMSA", "NASCAR", "MXGP")) "Racing" else if (canonical == "WRESTLING") "Wrestling" else canonical,
                canonical,
                title,
                start,
                event.optString("strStatus").ifBlank { "Scheduled" },
                "pre",
                home,
                away,
                event.optString("strHomeTeamBadge"),
                event.optString("strAwayTeamBadge"),
                event.optString("strTVStation"),
                event.optString("strThumb").ifBlank { event.optString("strPoster") },
                fallback.officialUrl,
                extractYouTubeId(event.optString("strVideo").ifBlank { event.optString("strYoutube") })
            )
        }
        tsdbFallbackCache[fallback.canonicalLeague] = TsdbFallbackCache(now, out)
        return out
    }

'''

# Prefer a canonical-key function, but tolerate it being rewritten by another
# patch. Normalize/fetchEspn are stable fallbacks. The implementation itself does
# not depend on canonicalKey, so any of these anchors are safe.
anchors = [
    '    private fun canonicalKey(event: SportsEvent): String = listOf(',
    '    private fun normalize(value: String): String =',
    '    private fun fetchEspn(league: ScheduleLeague, window: ScheduleWindow):',
    '    private fun parseEspn(root: JSONObject, league: ScheduleLeague):'
]
for anchor in anchors:
    if anchor in s:
        s = s.replace(anchor, IMPLEMENTATION + anchor, 1)
        break
else:
    # Last safe fallback: insert immediately before the object's final brace.
    pos = s.rfind('\n}')
    if pos < 0:
        raise SystemExit('could not find safe insertion point for schedule backup implementation')
    s = s[:pos] + '\n' + IMPLEMENTATION + s[pos:]

SERVICE.write_text(s, encoding='utf-8')
print('Installed resilient long-tail schedule backups with caching and rewrite-tolerant anchors.')
