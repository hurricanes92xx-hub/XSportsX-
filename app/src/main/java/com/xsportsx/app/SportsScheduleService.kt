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

private data class ScheduleLeague(val league: String, val sport: String, val path: String, val officialUrl: String, val query: String = "")
private data class ScheduleWindow(val start: LocalDate, val end: LocalDate) {
    fun query(): String = if (start == end) start.format(DateTimeFormatter.BASIC_ISO_DATE) else "${start.format(DateTimeFormatter.BASIC_ISO_DATE)}-${end.format(DateTimeFormatter.BASIC_ISO_DATE)}"
}

object SportsScheduleService {
    private const val DAYS_AHEAD = 30
    private const val MAX_GAMES_PER_LEAGUE = 150
    private const val HTTP_TIMEOUT_MS = 4_500L
    private const val CONNECT_TIMEOUT_MS = 1_800
    // TSDB_LONG_TAIL_BACKUP_V1: long-tail metadata fallback remains non-blocking.

    private val ESPN_BASES = listOf(
        "https://site.web.api.espn.com/apis/site/v2",
        "https://site.api.espn.com/apis/site/v2"
    )
    private val ESPN_V3_BASES = listOf(
        "https://site.web.api.espn.com/apis/site/v3",
        "https://site.api.espn.com/apis/site/v3"
    )

    private val leagues = listOf(
        ScheduleLeague("NFL", "Football", "football/nfl", "https://www.nfl.com/"),
        ScheduleLeague("NBA", "Basketball", "basketball/nba", "https://www.nba.com/"),
        ScheduleLeague("WNBA", "Basketball", "basketball/wnba", "https://www.wnba.com/"),
        ScheduleLeague("NCAA FB", "Football", "football/college-football", "https://www.ncaa.com/sports/football/fbs", "groups=80"),
        ScheduleLeague("NCAA FCS", "Football", "football/college-football", "https://www.ncaa.com/sports/football/fcs", "groups=81"),
        ScheduleLeague("NCAA BB", "Basketball", "basketball/mens-college-basketball", "https://www.ncaa.com/sports/basketball-men/d1"),
        ScheduleLeague("NCAA WBB", "Basketball", "basketball/womens-college-basketball", "https://www.ncaa.com/sports/basketball-women/d1"),
        ScheduleLeague("MLB", "Baseball", "baseball/mlb", "https://www.mlb.com/"),
        ScheduleLeague("NCAA BASEBALL", "Baseball", "baseball/college-baseball", "https://www.ncaa.com/sports/baseball"),
        ScheduleLeague("NHL", "Hockey", "hockey/nhl", "https://www.nhl.com/"),
        ScheduleLeague("NCAA MEN HOCKEY", "Hockey", "hockey/mens-college-hockey", "https://www.ncaa.com/sports/icehockey-men/d1"),
        ScheduleLeague("NCAA WOMEN HOCKEY", "Hockey", "hockey/womens-college-hockey", "https://www.ncaa.com/sports/icehockey-women/d1"),
        ScheduleLeague("NCAA SOFTBALL", "Softball", "softball/college-softball", "https://www.ncaa.com/sports/softball"),
        ScheduleLeague("NCAA VB", "Volleyball", "volleyball/womens-college-volleyball", "https://www.ncaa.com/sports/volleyball-women/d1"),
        ScheduleLeague("NCAA MEN SOCCER", "Soccer", "soccer/usa.ncaa.m.1", "https://www.ncaa.com/sports/soccer-men/d1"),
        ScheduleLeague("NCAA WOMEN SOCCER", "Soccer", "soccer/usa.ncaa.w.1", "https://www.ncaa.com/sports/soccer-women/d1"),
        ScheduleLeague("NCAA MEN LAX", "Lacrosse", "lacrosse/mens-college-lacrosse", "https://www.ncaa.com/sports/lacrosse-men/d1"),
        ScheduleLeague("NCAA WOMEN LAX", "Lacrosse", "lacrosse/womens-college-lacrosse", "https://www.ncaa.com/sports/lacrosse-women/d1"),
        ScheduleLeague("MLS", "Soccer", "soccer/usa.1", "https://www.mlssoccer.com/"),
        ScheduleLeague("EPL", "Soccer", "soccer/eng.1", "https://www.premierleague.com/"),
        ScheduleLeague("LaLiga", "Soccer", "soccer/esp.1", "https://www.laliga.com/"),
        ScheduleLeague("Bundesliga", "Soccer", "soccer/ger.1", "https://www.bundesliga.com/"),
        ScheduleLeague("Serie A", "Soccer", "soccer/ita.1", "https://www.legaseriea.it/"),
        ScheduleLeague("Ligue 1", "Soccer", "soccer/fra.1", "https://www.ligue1.com/"),
        ScheduleLeague("UCL", "Soccer", "soccer/uefa.champions", "https://www.uefa.com/uefachampionsleague/"),
        ScheduleLeague("UEL", "Soccer", "soccer/uefa.europa", "https://www.uefa.com/uefaeuropaleague/"),
        ScheduleLeague("NWSL", "Soccer", "soccer/usa.nwsl", "https://www.nwslsoccer.com/"),
        ScheduleLeague("UFC", "MMA", "mma/ufc", "https://www.ufc.com/"),
        ScheduleLeague("BOXING", "Boxing", "boxing/boxing", "https://www.espn.com/boxing/")
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
        "COLLEGE MEN'S SOCCER" -> "NCAA MEN SOCCER"
        "COLLEGE WOMEN'S SOCCER" -> "NCAA WOMEN SOCCER"
        "COLLEGE WOMEN'S LACROSSE" -> "NCAA WOMEN LAX"
        "COLLEGE MEN'S LACROSSE" -> "NCAA MEN LAX"
        else -> label.trim().uppercase()
    }

    fun canonicalLeagueFor(label: String): String = normalizeLeague(label)

    val uiLeagueChoices: List<String> = listOf(
        "NFL", "NBA", "WNBA", "NCAA FB", "NCAA FCS", "NCAA BB", "NCAA WBB", "MLB", "NCAA BASEBALL", "NHL",
        "NCAA MEN HOCKEY", "NCAA WOMEN HOCKEY", "NCAA SOFTBALL", "NCAA VB", "NCAA MEN SOCCER", "NCAA WOMEN SOCCER",
        "NCAA MEN LAX", "NCAA WOMEN LAX", "MLS", "EPL", "LaLiga", "Bundesliga", "Serie A", "Ligue 1", "UCL", "UEL", "NWSL",
        "UFC", "BOXING"
    )

    suspend fun load(): List<SportsEvent> = withContext(Dispatchers.IO) {
        val today = LocalDate.now(ZoneId.systemDefault())
        val windows = buildWindows(today)
        val limiter = Semaphore(12)
        val results = coroutineScope { leagues.map { league -> async { loadLeague(league, windows, limiter) } }.awaitAll() }
        (results.flatten() + MonsterJamLiveResolver.loadLive())
            .filter { event -> event.league.equals("Monster Jam", true) || leagues.any { it.league == normalizeLeague(event.league) } && (event.isLive || event.isPregame() || event.isUpcoming) }
            .map { it.copy(league = normalizeLeague(it.league)) }
            .distinctBy { it.id.ifBlank { listOf(it.league, normalize(it.home), normalize(it.away), it.startUtc).joinToString("|") } }
            .sortedWith(compareBy<SportsEvent> { !(it.isLive || it.isPregame()) }.thenBy { it.startUtc })
    }

    private fun buildWindows(today: LocalDate): List<ScheduleWindow> {
        val windows = ArrayList<ScheduleWindow>(3)
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

    private suspend fun loadLeague(league: ScheduleLeague, windows: List<ScheduleWindow>, limiter: Semaphore): List<SportsEvent> = coroutineScope {
        windows.map { window -> async { limiter.withPermit { fetchWindowWithFallbacks(league, window) } } }.awaitAll().flatten()
            .filter { it.league.equals(league.league, true) }
            .distinctBy { canonicalKey(it) }
            .sortedBy { it.startUtc }
            .take(MAX_GAMES_PER_LEAGUE)
    }

    private suspend fun fetchWindowWithFallbacks(league: ScheduleLeague, window: ScheduleWindow): List<SportsEvent> {
        val primary = withTimeoutOrNull(HTTP_TIMEOUT_MS) { runCatching { fetchEspn(league, window) }.getOrDefault(emptyList()) }.orEmpty()
        if (primary.isNotEmpty()) return primary
        return withTimeoutOrNull(HTTP_TIMEOUT_MS) { runCatching { fetchEspnV3(league, window) }.getOrDefault(emptyList()) }.orEmpty()
    }

    private fun canonicalKey(event: SportsEvent): String = listOf(normalizeLeague(event.league), normalize(event.home), normalize(event.away), event.startUtc.take(16)).joinToString("|")
    private fun normalize(value: String): String = value.lowercase().replace(Regex("\\bfc\\b"), "").replace(Regex("[^a-z0-9]+"), " ").trim().replace(Regex("\\s+"), " ")

    private fun fetchEspn(league: ScheduleLeague, window: ScheduleWindow): List<SportsEvent> {
        for (base in ESPN_BASES) {
            val result = runCatching { parseEspn(JSONObject(http(buildUrl(base, league, window))), league) }.getOrDefault(emptyList())
            if (result.isNotEmpty()) return result
        }
        return emptyList()
    }

    private fun fetchEspnV3(league: ScheduleLeague, window: ScheduleWindow): List<SportsEvent> {
        for (base in ESPN_V3_BASES) {
            val result = runCatching { parseEspn(JSONObject(http(buildUrl(base, league, window))), league) }.getOrDefault(emptyList())
            if (result.isNotEmpty()) return result
        }
        return emptyList()
    }

    private fun buildUrl(base: String, league: ScheduleLeague, window: ScheduleWindow): String = buildString {
        append("$base/sports/${league.path}/scoreboard?dates=${window.query()}&limit=1000")
        if (league.query.isNotBlank()) append('&').append(league.query)
    }

    private fun parseEspn(root: JSONObject, league: ScheduleLeague): List<SportsEvent> {
        val events = root.optJSONArray("events") ?: root.optJSONObject("content")?.optJSONArray("events") ?: return emptyList()
        val out = ArrayList<SportsEvent>(events.length())
        for (i in 0 until events.length()) {
            val event = events.optJSONObject(i) ?: continue
            val competition = event.optJSONArray("competitions")?.optJSONObject(0) ?: continue
            val competitors = competition.optJSONArray("competitors") ?: continue
            var home = ""; var away = ""; var homeLogo = ""; var awayLogo = ""
            for (j in 0 until competitors.length()) {
                val competitor = competitors.optJSONObject(j) ?: continue
                val team = competitor.optJSONObject("team")
                val name = team?.optString("displayName")?.ifBlank { team.optString("shortDisplayName") }?.ifBlank { competitor.optString("displayName") } ?: competitor.optString("displayName")
                val logo = team?.optString("logo").orEmpty()
                if (competitor.optString("homeAway").equals("home", true)) { home = name; homeLogo = logo } else { away = name; awayLogo = logo }
            }
            val status = competition.optJSONObject("status") ?: event.optJSONObject("status") ?: JSONObject()
            val type = status.optJSONObject("type") ?: JSONObject()
            val state = type.optString("state").ifBlank { status.optString("state") }
            val detail = type.optString("shortDetail").ifBlank { type.optString("detail") }.ifBlank { type.optString("name") }
            val broadcasts = competition.optJSONArray("broadcasts")
            val broadcast = buildString {
                if (broadcasts != null) for (j in 0 until broadcasts.length()) {
                    val names = broadcasts.optJSONObject(j)?.optJSONArray("names") ?: continue
                    for (k in 0 until names.length()) { val name = names.optString(k); if (name.isNotBlank()) { if (isNotEmpty()) append(", "); append(name) } }
                }
            }
            val start = event.optString("date").ifBlank { competition.optString("startDate") }
            if (start.isBlank() || home.isBlank() || away.isBlank()) continue
            val rawName = event.optString("name").ifBlank { event.optString("shortName") }
            val title = rawName.ifBlank { "$away vs $home" }
            out += SportsEvent(event.optString("id"), league.sport, league.league, title, start, detail, state, home, away, homeLogo, awayLogo, broadcast, event.optString("image"), league.officialUrl, extractYouTubeId(event.optString("youtubeVideoId").ifBlank { event.optString("youtubeUrl") }))
        }
        return out
    }

    private fun extractYouTubeId(value: String): String {
        val v = value.trim()
        if (v.matches(Regex("[A-Za-z0-9_-]{11}"))) return v
        return Regex("(?:v=|youtu\\.be/|youtube\\.com/(?:embed/|shorts/))([A-Za-z0-9_-]{11})").find(v)?.groupValues?.getOrNull(1).orEmpty()
    }

    private fun http(target: String): String {
        val connection = (URL(target).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"; connectTimeout = CONNECT_TIMEOUT_MS; readTimeout = HTTP_TIMEOUT_MS.toInt(); instanceFollowRedirects = true
            setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/136.0 Mobile Safari/537.36")
            setRequestProperty("Accept", "application/json, text/plain, */*")
            setRequestProperty("Accept-Language", "en-US,en;q=0.9")
            setRequestProperty("Referer", "https://www.espn.com/")
            setRequestProperty("Connection", "keep-alive")
        }
        return try {
            val code = connection.responseCode
            if (code !in 200..299) error("Schedule HTTP $code from ${URL(target).host}")
            connection.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        } finally { connection.disconnect() }
    }
}
