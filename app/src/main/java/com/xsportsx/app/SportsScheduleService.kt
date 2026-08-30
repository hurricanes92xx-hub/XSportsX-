package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.text.SimpleDateFormat
import java.time.Instant
import java.util.Date
import java.util.Locale

/**
 * Schedule client for XSportsX.
 *
 * Render is the preferred live source, but the Android app must never turn a
 * Render cold start/outage into an empty league screen. The repository's
 * canonical schedule feed is refreshed by GitHub Actions and is therefore a
 * safe, fast fallback for the next-three-days UI.
 */
object SportsScheduleService {
    private const val DEFAULT_DAYS_AHEAD = 3
    private const val HTTP_TIMEOUT_MS = 8_000
    private const val MAX_ATTEMPTS = 2
    private const val SOURCE_URL = BuildConfig.SPORTS_SOURCE_URL
    private const val CANONICAL_FEED_URL =
        "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/android-app/data/schedule_feed.json"

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

        // Prefer the live normalized source. If Render is asleep, missing, or
        // returns an empty payload, fall back immediately to the canonical feed.
        repeat(MAX_ATTEMPTS) {
            val connection = runCatching { URL(target).openConnection() as HttpURLConnection }.getOrNull()
                ?: return@repeat
            connection.connectTimeout = HTTP_TIMEOUT_MS
            connection.readTimeout = HTTP_TIMEOUT_MS
            connection.requestMethod = "GET"
            connection.setRequestProperty("Accept", "application/json")
            connection.setRequestProperty("User-Agent", "XSportsX-Android/2.1")
            try {
                if (connection.responseCode in 200..299) {
                    val body = connection.inputStream.bufferedReader().use { it.readText() }
                    val parsed = parseEvents(JSONObject(body).optJSONArray("events") ?: JSONArray())
                    if (parsed.isNotEmpty()) return@withContext parsed
                }
            } catch (_: Exception) {
                // Canonical feed below is the deliberate outage/cold-start path.
            } finally {
                connection.disconnect()
            }
        }

        loadCanonicalFallback(league, daysAhead)
    }

    private fun loadCanonicalFallback(league: String?, daysAhead: Int): List<SportsEvent> {
        val connection = runCatching { URL(CANONICAL_FEED_URL).openConnection() as HttpURLConnection }.getOrNull()
            ?: return emptyList()
        connection.connectTimeout = 5_000
        connection.readTimeout = 8_000
        connection.requestMethod = "GET"
        connection.setRequestProperty("Accept", "application/json")
        connection.setRequestProperty("User-Agent", "XSportsX-Android/2.1")
        return try {
            if (connection.responseCode !in 200..299) return emptyList()
            val body = connection.inputStream.bufferedReader().use { it.readText() }
            parseCanonicalFeed(JSONObject(body), league, daysAhead)
        } catch (_: Exception) {
            emptyList()
        } finally {
            connection.disconnect()
        }
    }

    private fun parseCanonicalFeed(root: JSONObject, requestedLeague: String?, daysAhead: Int): List<SportsEvent> {
        val events = root.optJSONArray("events") ?: return emptyList()
        val wanted = requestedLeague?.let(::canonicalFeedNames)
        val now = System.currentTimeMillis() - 26L * 60L * 60L * 1000L
        val end = System.currentTimeMillis() + daysAhead.coerceIn(1, 7) * 86_400_000L
        val out = ArrayList<SportsEvent>(events.length())

        for (i in 0 until events.length()) {
            val item = events.optJSONObject(i) ?: continue
            val feedLeague = item.optString("league").trim()
            if (feedLeague.isBlank() || (wanted != null && feedLeague !in wanted)) continue

            val title = item.optString("title").trim()
            val startText = item.optString("start").trim()
            val parsedStart = parseCanonicalStart(startText) ?: continue
            val millis = parsedStart.toEpochMilli()
            if (millis < now || millis > end) continue

            val (away, home) = splitTeams(title)
            if (away.isBlank() || home.isBlank()) continue

            val tag = item.optString("tag").trim().uppercase().ifBlank { "UPCOMING" }
            val canonicalLeague = canonicalUiLeague(feedLeague)
            val stableId = "canonical:${canonicalLeague}:${away}:${home}:$startText"
            out += SportsEvent(
                id = stableId,
                sport = sportFor(canonicalLeague),
                league = canonicalLeague,
                title = "$away vs $home",
                startUtc = parsedStart.toString(),
                status = tag,
                state = when (tag) {
                    "LIVE" -> "in"
                    "FINAL", "POST" -> "post"
                    else -> "pre"
                },
                home = home,
                away = away,
                homeLogo = "",
                awayLogo = "",
                broadcast = "",
                artUrl = "",
                sourceUrl = "https://github.com/hurricanes92xx-hub/XSportsX-/blob/android-app/data/schedule_feed.json"
            )
        }

        return out
            .distinctBy { canonicalKey(it) }
            .sortedWith(compareBy<SportsEvent> { !(it.isLive || it.isPregame()) }.thenBy { it.startUtc })
    }

    private fun canonicalFeedNames(league: String): Set<String> = when (normalizeLeague(league)) {
        "WNBA" -> setOf("WNBA")
        "NCAA FB" -> setOf("NCAA FB")
        "NCAA FCS" -> setOf("NCAA FCS", "NCAA FB")
        "NCAA VB" -> setOf("NCAA Women's Volleyball")
        "NCAA MEN SOCCER" -> setOf("NCAA Men's Soccer")
        "NCAA WOMEN SOCCER" -> setOf("NCAA Women's Soccer")
        "NCAA MEN HOCKEY" -> setOf("NCAA Men's Hockey")
        "NCAA WOMEN HOCKEY" -> setOf("NCAA Women's Hockey")
        "NCAA SOFTBALL" -> setOf("NCAA Softball")
        "MLB" -> setOf("MLB")
        "NFL" -> setOf("NFL")
        "NHL" -> setOf("NHL")
        "NBA" -> setOf("NBA")
        "MLS" -> setOf("MLS")
        "EPL" -> setOf("EPL")
        "LIGUE 1" -> setOf("Ligue 1")
        "BUNDESLIGA" -> setOf("Bundesliga")
        "LALIGA" -> setOf("LaLiga")
        "SERIE A" -> setOf("Serie A")
        "UCL" -> setOf("UCL")
        "UFC" -> setOf("UFC")
        else -> setOf(league)
    }

    private fun canonicalUiLeague(feedLeague: String): String = when (feedLeague.trim().uppercase()) {
        "NCAA MEN'S SOCCER" -> "NCAA MEN SOCCER"
        "NCAA WOMEN'S SOCCER" -> "NCAA WOMEN SOCCER"
        "NCAA WOMEN'S VOLLEYBALL" -> "NCAA VB"
        "NCAA MEN'S HOCKEY" -> "NCAA MEN HOCKEY"
        "NCAA WOMEN'S HOCKEY" -> "NCAA WOMEN HOCKEY"
        "NCAA SOFTBALL" -> "NCAA SOFTBALL"
        else -> normalizeLeague(feedLeague)
    }

    private fun sportFor(league: String): String = when {
        league.contains("FOOTBALL") || league == "NFL" -> "football"
        league.contains("BASKETBALL") || league == "NBA" || league == "WNBA" -> "basketball"
        league.contains("SOCCER") || league == "MLS" || league == "EPL" || league == "LALIGA" || league == "BUNDESLIGA" || league == "SERIE A" || league == "LIGUE 1" || league == "UCL" -> "soccer"
        league.contains("HOCKEY") || league == "NHL" -> "hockey"
        league.contains("BASEBALL") || league == "MLB" -> "baseball"
        league.contains("VOLLEYBALL") || league == "NCAA VB" -> "volleyball"
        league.contains("SOFTBALL") -> "softball"
        else -> "sports"
    }

    private fun splitTeams(title: String): Pair<String, String> {
        val separators = listOf(" @ ", " vs ", " VS ", " at ", " AT ")
        for (separator in separators) {
            val index = title.indexOf(separator)
            if (index > 0) {
                return title.substring(0, index).trim() to title.substring(index + separator.length).trim()
            }
        }
        return "" to ""
    }

    private fun parseCanonicalStart(value: String): Instant? {
        runCatching { return Instant.parse(value) }
        return runCatching {
            val format = SimpleDateFormat("MM/dd/yyyy'T'HH:mm:ssX", Locale.US)
            format.isLenient = false
            format.parse(value)?.let { Date(it.time).toInstant() }
        }.getOrNull()
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
