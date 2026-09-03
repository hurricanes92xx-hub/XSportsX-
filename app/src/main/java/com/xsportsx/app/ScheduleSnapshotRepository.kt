package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import java.time.temporal.ChronoUnit

/** Single canonical schedule snapshot shared by Mobile and TV. */
object ScheduleSnapshotRepository {
    private const val SNAPSHOT_TTL_MS = 5 * 60_000L
    private const val LIVE_TTL_MS = 10_000L
    private const val UI_DAYS = 3
    private const val SNAPSHOT_DAYS = 7
    private const val MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&hydrate=team,linescore"
    private const val ESPN_MLB_LIVE_URL = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"

    private val snapshotMutex = Mutex()
    private val liveMutex = Mutex()
    @Volatile private var snapshotCache: CachedEvents? = null
    @Volatile private var liveCache: CachedEvents? = null

    private data class CachedEvents(val events: List<SportsEvent>, val loadedAtMs: Long)

    suspend fun all(force: Boolean = false): List<SportsEvent> {
        val cached = snapshotCache
        if (!force && cached != null && age(cached) < SNAPSHOT_TTL_MS) return cached.events

        return snapshotMutex.withLock {
            val again = snapshotCache
            if (!force && again != null && age(again) < SNAPSHOT_TTL_MS) return@withLock again.events

            val canonical = runCatching { CanonicalScheduleProvider.load(null, SNAPSHOT_DAYS) }.getOrDefault(emptyList())
            // MLB is independently authoritative so a stale/failed canonical feed cannot erase baseball.
            val mlb = runCatching { loadMlbSchedule(SNAPSHOT_DAYS) }.getOrDefault(emptyList())
            val normalized = normalize(canonical + mlb)
            if (normalized.isNotEmpty()) {
                snapshotCache = CachedEvents(normalized, System.currentTimeMillis())
                normalized
            } else again?.events.orEmpty()
        }
    }

    suspend fun upcoming(league: String? = null, force: Boolean = false): List<SportsEvent> {
        val canonical = league?.let(SportsScheduleService::canonicalLeagueFor)
        val now = Instant.now()
        val cutoff = now.plus(UI_DAYS.toLong(), ChronoUnit.DAYS)
        return all(force).asSequence()
            .filter { !it.isLive }
            .filter { event -> canonical == null || SportsScheduleService.canonicalLeagueFor(event.league) == canonical }
            .filter { event ->
                val start = runCatching { Instant.parse(event.startUtc) }.getOrNull() ?: return@filter false
                val localDate = start.atZone(java.time.ZoneId.systemDefault()).toLocalDate()
                val today = now.atZone(java.time.ZoneId.systemDefault()).toLocalDate()
                val dateOnly = event.startUtc.matches(Regex(".*T00:00:00(?:\\.000)?Z$"))
                val dateOnlyInWindow = dateOnly && !localDate.isBefore(today) && localDate.isBefore(today.plusDays(UI_DAYS.toLong()))
                dateOnlyInWindow || (!start.isBefore(now.minus(10, ChronoUnit.MINUTES)) && start.isBefore(cutoff))
            }
            .sortedBy { it.startUtc }
            .toList()
    }

    /** Near-real-time live path. Uses both MLB Stats API and ESPN as independent fallbacks. */
    suspend fun live(force: Boolean = false): List<SportsEvent> {
        val cached = liveCache
        if (!force && cached != null && age(cached) < LIVE_TTL_MS) return cached.events
        return liveMutex.withLock {
            val again = liveCache
            if (!force && again != null && age(again) < LIVE_TTL_MS) return@withLock again.events

            val feedLive = runCatching { CanonicalScheduleProvider.load(null, 1) }.getOrDefault(emptyList())
                .filter { it.isLive }
            // MLB's schedule date is the baseball/local game date, not UTC. After midnight UTC,
            // late-night games such as a 9:38 PM ET first pitch are still on yesterday's MLB date.
            // Query both UTC dates so the Live Games screen cannot lose those games at midnight.
            val mlbLive = runCatching { loadMlbSchedule(1, includePreviousUtcDay = true).filter { it.isLive } }.getOrDefault(emptyList())
            // Some Android/network paths can reach ESPN when MLB Stats API is unavailable.
            // Merge both so MLB never disappears merely because one provider is blocked.
            val espnMlbLive = runCatching { loadEspnMlbLive() }.getOrDefault(emptyList())
            val normalized = normalize(feedLive + mlbLive + espnMlbLive).filter { it.isLive }
            if (normalized.isNotEmpty()) {
                liveCache = CachedEvents(normalized, System.currentTimeMillis())
                normalized
            } else again?.events.orEmpty()
        }
    }

    private suspend fun loadMlbSchedule(daysAhead: Int, includePreviousUtcDay: Boolean = false): List<SportsEvent> = withContext(Dispatchers.IO) {
        val todayUtc = LocalDate.now(ZoneOffset.UTC)
        val startDate = if (includePreviousUtcDay) todayUtc.minusDays(1) else todayUtc
        val endDate = if (includePreviousUtcDay) todayUtc else todayUtc.plusDays(daysAhead.toLong().coerceAtLeast(1L) - 1L)
        val url = "$MLB_SCHEDULE_URL&startDate=$startDate&endDate=$endDate"
        val c = URL(url).openConnection() as HttpURLConnection
        c.connectTimeout = 1_500
        c.readTimeout = 2_500
        c.requestMethod = "GET"
        c.instanceFollowRedirects = true
        c.useCaches = false
        c.setRequestProperty("Accept", "application/json")
        c.setRequestProperty("Cache-Control", "no-cache, no-store, max-age=0")
        c.setRequestProperty("Pragma", "no-cache")
        c.setRequestProperty("User-Agent", "XSportsX/2.2 Android")
        return@withContext try {
            if (c.responseCode !in 200..299) return@withContext emptyList()
            val root = JSONObject(c.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() })
            val dates = root.optJSONArray("dates") ?: return@withContext emptyList()
            val out = ArrayList<SportsEvent>()
            for (i in 0 until dates.length()) {
                val games = dates.optJSONObject(i)?.optJSONArray("games") ?: continue
                for (j in 0 until games.length()) {
                    val game = games.optJSONObject(j) ?: continue
                    val status = game.optJSONObject("status") ?: continue
                    val abstractState = status.optString("abstractGameState").lowercase()
                    val detailedState = status.optString("detailedState").lowercase()
                    val live = abstractState == "live" || abstractState == "in progress" || detailedState == "live" || detailedState.contains("in progress")
                    val final = abstractState == "final" || detailedState == "final" || detailedState.contains("game over")
                    val teams = game.optJSONObject("teams") ?: continue
                    val awayTeam = teams.optJSONObject("away")?.optJSONObject("team")
                    val homeTeam = teams.optJSONObject("home")?.optJSONObject("team")
                    val away = awayTeam?.optString("name").orEmpty()
                    val home = homeTeam?.optString("name").orEmpty()
                    val start = game.optString("gameDate")
                    if (away.isBlank() || home.isBlank() || start.isBlank()) continue
                    val gamePk = game.optLong("gamePk", 0L)
                    out += SportsEvent(
                        id = if (gamePk > 0) "mlb-$gamePk" else "mlb-${start.take(16)}-$away-$home",
                        sport = "Baseball", league = "MLB", title = "$away @ $home", startUtc = start,
                        status = when { live -> "LIVE"; final -> "FINAL"; else -> "UPCOMING" },
                        state = when { live -> "in"; final -> "post"; else -> "pre" },
                        home = home, away = away,
                        homeLogo = homeTeam?.optString("link").orEmpty(), awayLogo = awayTeam?.optString("link").orEmpty(),
                        sourceUrl = if (gamePk > 0) "https://www.mlb.com/gameday/$gamePk" else "https://www.mlb.com/scores"
                    )
                }
            }
            out
        } finally { c.disconnect() }
    }

    private suspend fun loadEspnMlbLive(): List<SportsEvent> = withContext(Dispatchers.IO) {
        val todayUtc = LocalDate.now(ZoneOffset.UTC)
        val dates = listOf(todayUtc.minusDays(1), todayUtc).distinct()
        val out = ArrayList<SportsEvent>()
        for (date in dates) {
            val target = "$ESPN_MLB_LIVE_URL?dates=${date.toString().replace("-", "")}&limit=1000"
            val c = URL(target).openConnection() as HttpURLConnection
            c.connectTimeout = 1_500
            c.readTimeout = 2_500
            c.requestMethod = "GET"
            c.instanceFollowRedirects = true
            c.useCaches = false
            c.setRequestProperty("Accept", "application/json")
            c.setRequestProperty("Cache-Control", "no-cache, no-store, max-age=0")
            c.setRequestProperty("Pragma", "no-cache")
            c.setRequestProperty("User-Agent", "XSportsX/2.2 Android")
            try {
                if (c.responseCode !in 200..299) continue
                val root = JSONObject(c.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() })
                val events = root.optJSONArray("events") ?: continue
                for (i in 0 until events.length()) {
                    val event = events.optJSONObject(i) ?: continue
                    val competition = event.optJSONArray("competitions")?.optJSONObject(0) ?: continue
                    val status = competition.optJSONObject("status")?.optJSONObject("type")
                        ?: event.optJSONObject("status")?.optJSONObject("type") ?: continue
                    val state = status.optString("state").lowercase()
                    val detail = status.optString("detail").lowercase()
                    val live = state == "in" || detail.contains("in progress") || detail.contains("live")
                    if (!live) continue
                    val competitors = competition.optJSONArray("competitors") ?: continue
                    var home = ""
                    var away = ""
                    var homeLogo = ""
                    var awayLogo = ""
                    for (j in 0 until competitors.length()) {
                        val team = competitors.optJSONObject(j) ?: continue
                        val obj = team.optJSONObject("team") ?: continue
                        val name = obj.optString("shortDisplayName").ifBlank { obj.optString("displayName") }
                        val logo = obj.optString("logo")
                        if (team.optString("homeAway") == "home") { home = name; homeLogo = logo }
                        else if (team.optString("homeAway") == "away") { away = name; awayLogo = logo }
                    }
                    val start = event.optString("date")
                    if (home.isBlank() || away.isBlank() || start.isBlank()) continue
                    val id = event.optString("id")
                    out += SportsEvent(
                        id = if (id.isBlank()) "espn-mlb-${start.take(16)}-$away-$home" else "espn-mlb-$id",
                        sport = "Baseball", league = "MLB", title = "$away @ $home", startUtc = start,
                        status = "LIVE", state = "in", home = home, away = away,
                        homeLogo = homeLogo, awayLogo = awayLogo,
                        sourceUrl = if (id.isBlank()) "https://www.espn.com/mlb/scoreboard" else "https://www.espn.com/mlb/game/_/gameId/$id"
                    )
                }
            } finally { c.disconnect() }
        }
        out
    }

    fun clear() {
        snapshotCache = null
        liveCache = null
    }

    private fun age(cache: CachedEvents): Long = System.currentTimeMillis() - cache.loadedAtMs

    private fun normalize(events: List<SportsEvent>): List<SportsEvent> {
        val seen = LinkedHashSet<String>()
        return events
            .map { it.copy(league = SportsScheduleService.canonicalLeagueFor(it.league)) }
            .filter { seen.add(eventKey(it)) }
            .sortedWith(compareBy<SportsEvent> { !(it.isLive || it.isPregame()) }.thenBy { it.startUtc })
    }

    private fun eventKey(event: SportsEvent): String {
        fun clean(value: String): String = value.lowercase().replace(Regex("[^a-z0-9]+"), " ").trim().replace(Regex("\\s+"), " ")
        val teams = listOf(clean(event.away), clean(event.home)).sorted()
        val matchup = if (teams.any { it.isNotBlank() }) teams.joinToString("|") else clean(event.title)
        return "${clean(event.league)}|$matchup|${event.startUtc.take(16)}"
    }
}
