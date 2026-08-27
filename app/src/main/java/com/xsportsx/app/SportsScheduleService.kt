package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private data class ScheduleLeague(
    val league: String,
    val sport: String,
    val path: String,
    val officialUrl: String,
    val query: String = ""
)

private data class ScheduleWindow(val start: LocalDate, val end: LocalDate) {
    fun query(): String = if (start == end) {
        start.format(DateTimeFormatter.BASIC_ISO_DATE)
    } else {
        "${start.format(DateTimeFormatter.BASIC_ISO_DATE)}-${end.format(DateTimeFormatter.BASIC_ISO_DATE)}"
    }
}

object SportsScheduleService {
    private const val DAYS_AHEAD = 30
    private const val MAX_GAMES_PER_LEAGUE = 150
    private const val HTTP_TIMEOUT_MS = 4_500L
    private const val CONNECT_TIMEOUT_MS = 1_800

    /*
     * Keep the list explicit so every feed is assigned to one canonical UI
     * league. NCAA football is split at the ESPN group level so FBS/FCS can
     * never bleed into one another.
     */
    private val leagues = listOf(
        ScheduleLeague("NFL", "Football", "football/nfl", "https://www.nfl.com/"),
        ScheduleLeague("NBA", "Basketball", "basketball/nba", "https://www.nba.com/"),
        ScheduleLeague("NCAA FB", "Football", "football/college-football", "https://www.ncaa.com/sports/football/fbs", "groups=80"),
        ScheduleLeague("NCAA FCS", "Football", "football/college-football", "https://www.ncaa.com/sports/football/fcs", "groups=81"),
        ScheduleLeague("NCAA BB", "Basketball", "basketball/mens-college-basketball", "https://www.ncaa.com/sports/basketball-men/d1"),
        ScheduleLeague("NCAA WBB", "Basketball", "basketball/womens-college-basketball", "https://www.ncaa.com/sports/basketball-women/d1"),
        ScheduleLeague("MLB", "Baseball", "baseball/mlb", "https://www.mlb.com/"),
        ScheduleLeague("NHL", "Hockey", "hockey/nhl", "https://www.nhl.com/"),
        ScheduleLeague("UFC", "MMA", "mma/ufc", "https://www.ufc.com/"),
        ScheduleLeague("BOXING", "Boxing", "boxing/boxing", "https://www.boxing.com/")
    )

    fun normalizeLeague(label: String): String = when (label.trim().uppercase()) {
        "COLLEGE FOOTBALL", "NCAA FOOTBALL", "NCAAF", "NCAA FBS" -> "NCAA FB"
        "COLLEGE FCS", "NCAA FOOTBALL CHAMPIONSHIP", "NCAA FCS FOOTBALL" -> "NCAA FCS"
        "COLLEGE BASKETBALL", "NCAA MEN", "NCAAM" -> "NCAA BB"
        "NCAA WOMEN", "NCAAW" -> "NCAA WBB"
        "COLLEGE BASEBALL" -> "NCAA BASEBALL"
        "COLLEGE SOFTBALL" -> "NCAA SOFTBALL"
        "COLLEGE MEN'S HOCKEY" -> "NCAA MEN HOCKEY"
        "COLLEGE WOMEN'S HOCKEY" -> "NCAA WOMEN HOCKEY"
        "COLLEGE WOMEN'S LACROSSE" -> "NCAA WOMEN LAX"
        "COLLEGE WRESTLING" -> "NCAA WRESTLING"
        "COLLEGE MEN'S SOCCER" -> "NCAA MEN SOCCER"
        "COLLEGE WOMEN'S SOCCER" -> "NCAA WOMEN SOCCER"
        "FORMULA 1", "FORMULA1" -> "F1"
        "MOTO GP", "MOTOGP" -> "MOTOGP"
        "FORMULA E", "FORMULAE" -> "FORMULA E"
        "MONSTER JAM", "MONSTERJAM" -> "MONSTER JAM"
        else -> label.trim().uppercase()
    }

    fun canonicalLeagueFor(label: String): String = normalizeLeague(label)

    val uiLeagueChoices: List<String> = listOf(
        "NFL", "NBA", "NCAA FB", "NCAA FCS", "NCAA BB", "NCAA WBB", "MLB", "NCAA BASEBALL",
        "NHL", "NCAA MEN HOCKEY", "NCAA WOMEN HOCKEY", "NCAA SOFTBALL", "UFC", "BOXING",
        "NCAA VB", "NCAA MEN SOCCER", "NCAA WOMEN SOCCER", "NCAA MEN LAX", "NCAA WOMEN LAX",
        "NCAA WRESTLING", "MLS", "EPL", "LaLiga", "Bundesliga", "Serie A", "Ligue 1",
        "UCL", "UEL", "NWSL", "RUGBY", "WRESTLING", "MOTOGP", "WRC", "WEC", "IMSA",
        "FORMULA E", "MXGP", "MONSTER JAM", "F1", "NASCAR", "INDYCAR"
    )

    suspend fun load(): List<SportsEvent> = withContext(Dispatchers.IO) {
        val today = LocalDate.now(ZoneId.systemDefault())
        val windows = buildWindows(today)
        // A failed request now affects only that league/window. There is no
        // global timeout capable of turning a partial schedule into zero games.
        val limiter = Semaphore(12)

        val results = coroutineScope {
            leagues.map { league ->
                async {
                    loadLeague(league, windows, limiter)
                }
            }.awaitAll()
        }

        results.flatten()
            .filter { event ->
                val league = normalizeLeague(event.league)
                val knownLeague = leagues.any { it.league == league }
                knownLeague && (event.isLive || event.isPregame() || event.isUpcoming)
            }
            .map { it.copy(league = normalizeLeague(it.league)) }
            .distinctBy { event ->
                event.id.ifBlank {
                    listOf(event.league, normalize(event.home), normalize(event.away), event.startUtc).joinToString("|")
                }
            }
            .sortedWith(
                compareBy<SportsEvent> { !(it.isLive || it.isPregame()) }
                    .thenBy { it.startUtc }
            )
    }

    private fun buildWindows(today: LocalDate): List<ScheduleWindow> {
        val windows = ArrayList<ScheduleWindow>(3)
        // Fetch today separately for the lowest possible live-score latency.
        windows += ScheduleWindow(today, today)

        var cursor = today.plusDays(1)
        val end = today.plusDays(DAYS_AHEAD.toLong())
        while (!cursor.isAfter(end)) {
            val windowEnd = minOf(cursor.plusDays(13), end)
            windows += ScheduleWindow(cursor, windowEnd)
            cursor = windowEnd.plusDays(1)
        }
        return windows
    }

    private suspend fun loadLeague(
        league: ScheduleLeague,
        windows: List<ScheduleWindow>,
        limiter: Semaphore
    ): List<SportsEvent> = coroutineScope {
        windows.map { window ->
            async {
                limiter.withPermit {
                    fetchWindowWithFallbacks(league, window)
                }
            }
        }.awaitAll().flatten()
            .filter { it.league.equals(league.league, true) }
            .distinctBy { canonicalKey(it) }
            .sortedBy { it.startUtc }
            .take(MAX_GAMES_PER_LEAGUE)
    }

    private suspend fun fetchWindowWithFallbacks(
        league: ScheduleLeague,
        window: ScheduleWindow
    ): List<SportsEvent> {
        val primary = withTimeoutOrNull(HTTP_TIMEOUT_MS) {
            runCatching { fetchEspn(league, window) }.getOrDefault(emptyList())
        }.orEmpty()

        if (primary.isNotEmpty()) return primary

        // V3 is isolated to the failed/empty window instead of replacing the
        // whole schedule load. This keeps the UI populated when one endpoint
        // has a transient response problem.
        return withTimeoutOrNull(HTTP_TIMEOUT_MS) {
            runCatching { fetchEspnV3(league, window) }.getOrDefault(emptyList())
        }.orEmpty()
    }

    private fun canonicalKey(event: SportsEvent): String = listOf(
        normalizeLeague(event.league),
        normalize(event.home),
        normalize(event.away),
        event.startUtc.take(16)
    ).joinToString("|")

    private fun normalize(value: String): String = value.lowercase()
        .replace(Regex("\\bfc\\b"), "")
        .replace(Regex("[^a-z0-9]+"), " ")
        .trim()
        .replace(Regex("\\s+"), " ")

    private fun fetchEspn(league: ScheduleLeague, window: ScheduleWindow): List<SportsEvent> =
        parseEspn(
            JSONObject(http(buildUrl("https://site.api.espn.com/apis/site/v2", league, window))),
            league
        )

    private fun fetchEspnV3(league: ScheduleLeague, window: ScheduleWindow): List<SportsEvent> =
        parseEspn(
            JSONObject(http(buildUrl("https://site.api.espn.com/apis/site/v3", league, window))),
            league
        )

    private fun buildUrl(base: String, league: ScheduleLeague, window: ScheduleWindow): String {
        val query = buildString {
            append("dates=")
            append(window.query())
            append("&limit=1000")
            if (league.query.isNotBlank()) {
                append('&')
                append(league.query)
            }
        }
        return "$base/sports/${league.path}/scoreboard?$query"
    }

    private fun parseEspn(root: JSONObject, league: ScheduleLeague): List<SportsEvent> {
        val events = root.optJSONArray("events")
            ?: root.optJSONObject("content")?.optJSONArray("events")
            ?: return emptyList()

        val out = ArrayList<SportsEvent>(events.length())
        for (i in 0 until events.length()) {
            val event = events.optJSONObject(i) ?: continue
            val competition = event.optJSONArray("competitions")?.optJSONObject(0) ?: continue
            val competitors = competition.optJSONArray("competitors") ?: continue

            var home = ""
            var away = ""
            var homeLogo = ""
            var awayLogo = ""

            for (j in 0 until competitors.length()) {
                val competitor = competitors.optJSONObject(j) ?: continue
                val team = competitor.optJSONObject("team")
                val name = team?.optString("displayName")
                    ?.ifBlank { team.optString("shortDisplayName") }
                    ?.ifBlank { competitor.optString("displayName") }
                    ?: competitor.optString("displayName")
                val logo = team?.optString("logo").orEmpty()

                if (competitor.optString("homeAway").equals("home", true)) {
                    home = name
                    homeLogo = logo
                } else {
                    away = name
                    awayLogo = logo
                }
            }

            val status = competition.optJSONObject("status")
                ?: event.optJSONObject("status")
                ?: JSONObject()
            val type = status.optJSONObject("type") ?: JSONObject()
            val state = type.optString("state").ifBlank { status.optString("state") }
            val detail = type.optString("shortDetail")
                .ifBlank { type.optString("detail") }
                .ifBlank { type.optString("name") }

            val broadcasts = competition.optJSONArray("broadcasts")
            val broadcast = buildString {
                if (broadcasts != null) {
                    for (j in 0 until broadcasts.length()) {
                        val names = broadcasts.optJSONObject(j)?.optJSONArray("names") ?: continue
                        for (k in 0 until names.length()) {
                            val name = names.optString(k)
                            if (name.isBlank()) continue
                            if (isNotEmpty()) append(", ")
                            append(name)
                        }
                    }
                }
            }

            val start = event.optString("date")
                .ifBlank { competition.optString("startDate") }
            if (start.isBlank() || home.isBlank() || away.isBlank()) continue

            val rawName = event.optString("name")
                .ifBlank { event.optString("shortName") }
            val title = rawName.ifBlank { "$away vs $home" }

            val youtube = event.optString("youtubeVideoId")
                .ifBlank { event.optString("youtubeUrl") }
                .let(::extractYouTubeId)

            out += SportsEvent(
                event.optString("id"),
                league.sport,
                league.league,
                title,
                start,
                detail,
                state,
                home,
                away,
                homeLogo,
                awayLogo,
                broadcast,
                event.optString("image"),
                league.officialUrl,
                youtube
            )
        }
        return out
    }

    private fun extractYouTubeId(value: String): String {
        val v = value.trim()
        if (v.matches(Regex("[A-Za-z0-9_-]{11}"))) return v
        return Regex(
            "(?:v=|youtu\\.be/|youtube\\.com/(?:embed/|shorts/))([A-Za-z0-9_-]{11})"
        ).find(v)?.groupValues?.getOrNull(1).orEmpty()
    }

    private fun http(target: String): String {
        val connection = (URL(target).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = CONNECT_TIMEOUT_MS
            readTimeout = HTTP_TIMEOUT_MS.toInt()
            instanceFollowRedirects = true
            setRequestProperty("User-Agent", "XSportsX/1.5 (Android)")
            setRequestProperty("Accept", "application/json,text/plain,*/*")
            setRequestProperty("Accept-Encoding", "gzip")
        }

        return try {
            val code = connection.responseCode
            if (code !in 200..299) error("Schedule HTTP $code")
            connection.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        } finally {
            connection.disconnect()
        }
    }
}
