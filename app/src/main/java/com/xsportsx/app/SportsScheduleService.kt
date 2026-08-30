package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/**
 * Thin client for the external XSportsX Sports Source.
 *
 * Mobile and TV use this single source for schedule data. The source owns
 * provider selection, normalization, caching and refresh.
 */
object SportsScheduleService {
    private const val DEFAULT_DAYS_AHEAD = 3
    // Render free services can cold-start; 15s prevents a healthy source from
    // being reported as unavailable while the container is waking up.
    private const val HTTP_TIMEOUT_MS = 15_000
    private const val MAX_ATTEMPTS = 2
    private const val SOURCE_URL = BuildConfig.SPORTS_SOURCE_URL

    private val uiChoices = listOf(
        "NFL", "NBA", "WNBA", "NCAA FB", "NCAA FCS", "NCAA BB", "NCAA WBB", "MLB", "NCAA BASEBALL", "NHL",
        "NCAA MEN HOCKEY", "NCAA WOMEN HOCKEY", "NCAA SOFTBALL", "NCAA VB", "NCAA MEN SOCCER", "NCAA WOMEN SOCCER",
        "NCAA MEN LAX", "NCAA WOMEN LAX", "MLS", "EPL", "LaLiga", "Bundesliga", "Serie A", "Ligue 1", "UCL", "UEL", "NWSL",
        "UFC", "BOXING"
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
        "COLLEGE MEN'S SOCCER", "NCAA MEN'S SOCCER" -> "NCAA MEN SOCCER"
        "COLLEGE WOMEN'S SOCCER", "NCAA WOMEN'S SOCCER" -> "NCAA WOMEN SOCCER"
        "COLLEGE WOMEN'S LACROSSE" -> "NCAA WOMEN LAX"
        "COLLEGE MEN'S LACROSSE" -> "NCAA MEN LAX"
        "NCAA VOLLEYBALL", "COLLEGE VOLLEYBALL" -> "NCAA VB"
        else -> label.trim().uppercase()
    }

    fun canonicalLeagueFor(label: String): String = normalizeLeague(label)
    val uiLeagueChoices: List<String> = uiChoices

    suspend fun load(): List<SportsEvent> = fetchSchedule(null, DEFAULT_DAYS_AHEAD)
    suspend fun loadBackground(): List<SportsEvent> = fetchSchedule(null, 7)
    suspend fun loadForLeague(label: String, daysAhead: Int = DEFAULT_DAYS_AHEAD): List<SportsEvent> =
        fetchSchedule(normalizeLeague(label), daysAhead)

    private suspend fun fetchSchedule(league: String?, daysAhead: Int): List<SportsEvent> = withContext(Dispatchers.IO) {
        val query = buildString {
            append("days=")
            append(daysAhead.coerceIn(1, 7))
            if (!league.isNullOrBlank()) {
                append("&league=")
                append(URLEncoder.encode(league, Charsets.UTF_8.name()))
            }
        }
        val target = "${SOURCE_URL.trimEnd('/')}/api/schedule?$query"

        repeat(MAX_ATTEMPTS) { attempt ->
            val connection = runCatching { URL(target).openConnection() as HttpURLConnection }.getOrNull()
                ?: return@repeat
            connection.connectTimeout = HTTP_TIMEOUT_MS
            connection.readTimeout = HTTP_TIMEOUT_MS
            connection.requestMethod = "GET"
            connection.setRequestProperty("Accept", "application/json")
            connection.setRequestProperty("User-Agent", "XSportsX-Android/2.0")
            try {
                if (connection.responseCode in 200..299) {
                    val body = connection.inputStream.bufferedReader().use { it.readText() }
                    val parsed = parseEvents(JSONObject(body).optJSONArray("events") ?: JSONArray())
                    if (parsed.isNotEmpty() || attempt == MAX_ATTEMPTS - 1) return@withContext parsed
                }
            } catch (_: Exception) {
                if (attempt == MAX_ATTEMPTS - 1) return@withContext emptyList()
            } finally {
                connection.disconnect()
            }
        }
        emptyList()
    }

    private fun parseEvents(events: JSONArray): List<SportsEvent> {
        val out = ArrayList<SportsEvent>(events.length())
        for (i in 0 until events.length()) {
            val item = events.optJSONObject(i) ?: continue
            val id = item.optString("id").trim()
            val home = item.optString("home").trim()
            val away = item.optString("away").trim()
            val start = item.optString("startUtc").trim()
            if (id.isBlank() || home.isBlank() || away.isBlank() || start.isBlank()) continue
            out += SportsEvent(
                id = id,
                sport = item.optString("sport"),
                league = normalizeLeague(item.optString("league")),
                title = item.optString("title").ifBlank { "$away vs $home" },
                startUtc = start,
                status = item.optString("status"),
                state = item.optString("state"),
                home = home,
                away = away,
                homeLogo = item.optString("homeLogo"),
                awayLogo = item.optString("awayLogo"),
                broadcast = item.optString("broadcast"),
                artUrl = item.optString("artUrl"),
                sourceUrl = item.optString("sourceUrl")
            )
        }
        return out
            .distinctBy { canonicalKey(it) }
            .sortedWith(compareBy<SportsEvent> { !(it.isLive || it.isPregame()) }.thenBy { it.startUtc })
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
}
