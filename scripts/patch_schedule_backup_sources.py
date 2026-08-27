#!/usr/bin/env python3
from pathlib import Path

SERVICE = Path('app/src/main/java/com/xsportsx/app/SportsScheduleService.kt')
s = SERVICE.read_text(encoding='utf-8')

MARKER = 'TSDB_LONG_TAIL_BACKUP_V1'
if MARKER in s:
    print('Schedule backup sources already present')
    raise SystemExit(0)

model_anchor = 'private data class ScheduleWindow(val start: LocalDate, val end: LocalDate) {'
model = '''private data class TsdbFallbackLeague(
    val canonicalLeague: String,
    val leagueId: Int,
    val season: String,
    val officialUrl: String
)

private data class TsdbFallbackCache(
    val loadedAtMs: Long,
    val events: List<SportsEvent>
)

'''
if model_anchor not in s:
    raise SystemExit('schedule window model anchor not found')
s = s.replace(model_anchor, model + model_anchor, 1)

constants_anchor = '    private const val CONNECT_TIMEOUT_MS = 1_800\n'
constants = '''    // TSDB_LONG_TAIL_BACKUP_V1
    // TheSportsDB is intentionally last-resort only. ESPN/official feeds stay primary.
    private const val TSDB_API_BASE = "https://www.thesportsdb.com/api/v1/json/123"
    private const val TSDB_CACHE_MS = 15L * 60L * 1000L
    private const val TSDB_BACKUP_TIMEOUT_MS = 2_500L
    private val tsdbFallbackCache = java.util.concurrent.ConcurrentHashMap<String, TsdbFallbackCache>()
    private val tsdbFallbackLeagues = listOf(
        TsdbFallbackLeague("F1", 4370, "2026", "https://www.formula1.com/"),
        TsdbFallbackLeague("FORMULA E", 4371, "2025-2026", "https://www.fiaformulae.com/"),
        TsdbFallbackLeague("INDYCAR", 4373, "2026", "https://www.indycar.com/"),
        TsdbFallbackLeague("MOTOGP", 4407, "2026", "https://www.motogp.com/"),
        TsdbFallbackLeague("WRC", 4409, "2026", "https://www.fia.com/events/world-rally-championship/season-2026/events-calendar"),
        TsdbFallbackLeague("WEC", 4413, "2026", "https://www.fiawec.com/"),
        TsdbFallbackLeague("IMSA", 4488, "2026", "https://www.imsa.com/"),
        TsdbFallbackLeague("NASCAR", 4393, "2026", "https://www.nascar.com/"),
        TsdbFallbackLeague("MXGP", 4587, "2026", "https://www.mxgp.com/calendar"),
        TsdbFallbackLeague("UFC", 4443, "2026", "https://www.ufc.com/watch/schedule"),
        TsdbFallbackLeague("BOXING", 4445, "2026", "https://www.espn.com/boxing/story/_/id/12508267/boxing-schedule"),
        TsdbFallbackLeague("WRESTLING", 4444, "2026", "https://www.wwe.com/article/wwe-upcoming-events"),
        TsdbFallbackLeague("WRESTLING_ROH", 4448, "2026", "https://www.allelitewrestling.com/"),
        TsdbFallbackLeague("WRESTLING_NJPW", 4449, "2026", "https://www.njpw.co.jp/event-calendar"),
        TsdbFallbackLeague("WRESTLING_TNA", 4455, "2026", "https://tnawrestling.com/events/")
    )
'''
if constants_anchor not in s:
    raise SystemExit('schedule timeout constants anchor not found')
s = s.replace(constants_anchor, constants_anchor + constants, 1)

if 'fetchTheSportsDbLongTailFallbacks()' not in s:
    if '(results.flatten() + fetchSpecialScheduleFeed())' in s:
        s = s.replace(
            '(results.flatten() + fetchSpecialScheduleFeed())',
            '(results.flatten() + fetchSpecialScheduleFeed() + fetchTheSportsDbLongTailFallbacks())',
            1,
        )
    elif '        results.flatten()\n' in s:
        s = s.replace(
            '        results.flatten()\n',
            '        (results.flatten() + fetchTheSportsDbLongTailFallbacks())\n',
            1,
        )
    else:
        raise SystemExit('schedule result merge anchor not found')

if 'TSDB_LONG_TAIL_LEAGUES' not in s:
    anchor = '    val uiLeagueChoices: List<String> = listOf(\n'
    inject = '''    private val TSDB_LONG_TAIL_LEAGUES = setOf(
        "F1", "FORMULA E", "INDYCAR", "MOTOGP", "WRC", "WEC", "IMSA", "NASCAR",
        "MXGP", "UFC", "BOXING", "WRESTLING"
    )

'''
    if anchor not in s:
        raise SystemExit('league choices anchor not found')
    s = s.replace(anchor, inject + anchor, 1)

old_known = '(knownLeague || SPECIAL_FEED_LEAGUES.contains(league))'
if old_known in s and 'TSDB_LONG_TAIL_LEAGUES.contains(league)' not in s:
    s = s.replace(
        old_known,
        '(knownLeague || SPECIAL_FEED_LEAGUES.contains(league) || TSDB_LONG_TAIL_LEAGUES.contains(league))',
        1,
    )
elif 'knownLeague && (event.isLive || event.isPregame() || event.isUpcoming)' in s:
    s = s.replace(
        'knownLeague && (event.isLive || event.isPregame() || event.isUpcoming)',
        '(knownLeague || TSDB_LONG_TAIL_LEAGUES.contains(league)) && (event.isLive || event.isPregame() || event.isUpcoming)',
        1,
    )

implementation_anchor = '    private fun canonicalKey(event: SportsEvent): String = listOf(\n'
implementation = r'''    private suspend fun fetchTheSportsDbLongTailFallbacks(): List<SportsEvent> = coroutineScope {
        tsdbFallbackLeagues
            .map { fallback ->
                async {
                    withTimeoutOrNull(TSDB_BACKUP_TIMEOUT_MS) {
                        runCatching { fetchTheSportsDbFallback(fallback) }.getOrDefault(emptyList())
                    }.orEmpty()
                }
            }
            .awaitAll()
            .flatten()
            .distinctBy { canonicalKey(it) }
    }

    private fun fetchTheSportsDbFallback(fallback: TsdbFallbackLeague): List<SportsEvent> {
        val now = System.currentTimeMillis()
        val cached = tsdbFallbackCache[fallback.canonicalLeague]
        if (cached != null && now - cached.loadedAtMs < TSDB_CACHE_MS) return cached.events

        val target = "$TSDB_API_BASE/eventsnextleague.php?id=${fallback.leagueId}"
        val root = JSONObject(http(target))
        val events = root.optJSONArray("events") ?: return emptyList()
        val out = ArrayList<SportsEvent>(events.length())
        for (i in 0 until events.length()) {
            val event = events.optJSONObject(i) ?: continue
            val date = event.optString("dateEvent").trim()
            if (date.isBlank()) continue
            val time = event.optString("strTime").trim().ifBlank { "00:00:00" }
            val start = if (event.optString("strTimestamp").isNotBlank()) {
                event.optString("strTimestamp")
            } else {
                "${date}T${time}Z"
            }

            val rawLeague = event.optString("strLeague").uppercase()
            val canonical = when {
                fallback.canonicalLeague.startsWith("WRESTLING") -> "WRESTLING"
                else -> fallback.canonicalLeague
            }
            if (rawLeague.isBlank() && canonical.isBlank()) continue

            val eventName = event.optString("strEvent").ifBlank { canonical }
            val home = event.optString("strHomeTeam").ifBlank { eventName }
            val away = event.optString("strAwayTeam").ifBlank { canonical }
            val status = event.optString("strStatus").ifBlank { "Scheduled" }
            val poster = event.optString("strThumb").ifBlank { event.optString("strPoster") }
            val youtube = extractYouTubeId(event.optString("strVideo").ifBlank { event.optString("strYoutube") })

            out += SportsEvent(
                "tsdb-${fallback.leagueId}-${event.optString("idEvent").ifBlank { i.toString() }}",
                if (canonical in setOf("F1", "FORMULA E", "INDYCAR", "MOTOGP", "WRC", "WEC", "IMSA", "NASCAR", "MXGP")) "Racing" else if (canonical == "WRESTLING") "Wrestling" else fallback.canonicalLeague,
                canonical,
                eventName,
                start,
                status,
                "pre",
                home,
                away,
                event.optString("strHomeTeamBadge"),
                event.optString("strAwayTeamBadge"),
                event.optString("strTVStation"),
                poster,
                fallback.officialUrl,
                youtube
            )
        }

        tsdbFallbackCache[fallback.canonicalLeague] = TsdbFallbackCache(now, out)
        return out
    }

'''
if implementation_anchor not in s:
    raise SystemExit('canonical key anchor not found')
s = s.replace(implementation_anchor, implementation + implementation_anchor, 1)

SERVICE.write_text(s, encoding='utf-8')
print('Installed safe long-tail TheSportsDB fallback sources with caching and last-resort ordering.')
