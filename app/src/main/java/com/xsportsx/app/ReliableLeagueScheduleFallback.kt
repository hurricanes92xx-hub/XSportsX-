package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter

/**
 * Recovery path for league screens.
 *
 * The legacy service fans four daily ESPN requests out in parallel. ESPN's
 * public scoreboard endpoints are known to throttle under request bursts, so
 * this recovery path deliberately uses one range request first and, only when
 * that fails, sequential one-day requests. It also keeps the last good result
 * in memory so a transient empty response never wipes a healthy schedule.
 */
object ReliableLeagueScheduleFallback {
    private const val CONNECT_TIMEOUT_MS = 3_000
    private const val READ_TIMEOUT_MS = 8_000
    private const val MAX_EVENTS = 2_000

    private val lastKnownGood = mutableMapOf<String, List<SportsEvent>>()

    private data class Endpoint(
        val canonical: String,
        val sport: String,
        val league: String,
        val query: String = ""
    )

    private val endpoints = mapOf(
        "NFL" to Endpoint("NFL", "football", "nfl"),
        "NBA" to Endpoint("NBA", "basketball", "nba"),
        "WNBA" to Endpoint("WNBA", "basketball", "wnba"),
        "NCAA FB" to Endpoint("NCAA FB", "football", "college-football", "groups=80"),
        "NCAA FCS" to Endpoint("NCAA FCS", "football", "college-football", "groups=81"),
        "NCAA BB" to Endpoint("NCAA BB", "basketball", "mens-college-basketball"),
        "NCAA WBB" to Endpoint("NCAA WBB", "basketball", "womens-college-basketball"),
        "MLB" to Endpoint("MLB", "baseball", "mlb"),
        "NCAA BASEBALL" to Endpoint("NCAA BASEBALL", "baseball", "college-baseball"),
        "NHL" to Endpoint("NHL", "hockey", "nhl"),
        "NCAA VB" to Endpoint("NCAA VB", "volleyball", "womens-college-volleyball"),
        "MLS" to Endpoint("MLS", "soccer", "usa.1"),
        "EPL" to Endpoint("EPL", "soccer", "eng.1"),
        "LALIGA" to Endpoint("LALIGA", "soccer", "esp.1"),
        "BUNDESLIGA" to Endpoint("BUNDESLIGA", "soccer", "ger.1"),
        "SERIE A" to Endpoint("SERIE A", "soccer", "ita.1"),
        "LIGUE 1" to Endpoint("LIGUE 1", "soccer", "fra.1"),
        "UCL" to Endpoint("UCL", "soccer", "uefa.champions"),
        "UEL" to Endpoint("UEL", "soccer", "uefa.europa"),
        "NWSL" to Endpoint("NWSL", "soccer", "usa.nwsl"),
        "UFC" to Endpoint("UFC", "mma", "ufc"),
        "BOXING" to Endpoint("BOXING", "boxing", "boxing")
    )

    suspend fun load(leagueLabel: String, daysAhead: Int = 3): List<SportsEvent> = withContext(Dispatchers.IO) {
        val canonical = SportsScheduleService.canonicalLeagueFor(leagueLabel)
        val endpoint = endpoints[canonical] ?: return@withContext lastKnownGood[canonical].orEmpty()
        val today = LocalDate.now(ZoneId.systemDefault())
        val end = today.plusDays(daysAhead.toLong())

        val range = runCatching { fetch(endpoint, today, end) }.getOrDefault(emptyList())
        val events = if (range.isNotEmpty()) {
            range
        } else {
            // ESPN is more reliable when requests are serialized rather than bursty.
            buildList {
                var day = today
                while (!day.isAfter(end)) {
                    addAll(runCatching { fetch(endpoint, day, day) }.getOrDefault(emptyList()))
                    day = day.plusDays(1)
                }
            }
        }

        val normalized = events
            .filter { SportsScheduleService.canonicalLeagueFor(it.league) == canonical || it.league.equals(canonical, true) }
            .map { it.copy(league = canonical) }
            .distinctBy { key(it) }
            .sortedBy { it.startUtc }
            .take(MAX_EVENTS)

        if (normalized.isNotEmpty()) lastKnownGood[canonical] = normalized
        normalized.ifEmpty { lastKnownGood[canonical].orEmpty() }
    }

    private fun fetch(endpoint: Endpoint, start: LocalDate, end: LocalDate): List<SportsEvent> {
        val query = buildString {
            append("dates=")
            append(start.format(DateTimeFormatter.BASIC_ISO_DATE))
            if (end != start) {
                append('-')
                append(end.format(DateTimeFormatter.BASIC_ISO_DATE))
            }
            append("&limit=1000")
            if (endpoint.query.isNotBlank()) append('&').append(endpoint.query)
        }
        val url = "https://site.api.espn.com/apis/site/v2/sports/${endpoint.sport}/${endpoint.league}/scoreboard?$query"
        val body = http(url)
        val root = JSONObject(body)
        val events = root.optJSONArray("events") ?: return emptyList()
        val result = ArrayList<SportsEvent>(events.length())

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
                val name = team?.optString("displayName")?.ifBlank { team.optString("shortDisplayName") }
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

            val startUtc = event.optString("date").ifBlank { competition.optString("startDate") }
            if (startUtc.isBlank() || home.isBlank() || away.isBlank()) continue

            val status = competition.optJSONObject("status") ?: event.optJSONObject("status") ?: JSONObject()
            val type = status.optJSONObject("type") ?: JSONObject()
            val state = type.optString("state").ifBlank { status.optString("state") }
            val detail = type.optString("shortDetail")
                .ifBlank { type.optString("detail") }
                .ifBlank { type.optString("name") }

            val broadcasts = competition.optJSONArray("broadcasts")
            val broadcast = buildString {
                if (broadcasts != null) for (j in 0 until broadcasts.length()) {
                    val names = broadcasts.optJSONObject(j)?.optJSONArray("names") ?: continue
                    for (k in 0 until names.length()) {
                        val name = names.optString(k)
                        if (name.isNotBlank()) {
                            if (isNotEmpty()) append(", ")
                            append(name)
                        }
                    }
                }
            }

            result += SportsEvent(
                id = event.optString("id"),
                sport = endpoint.sport,
                league = endpoint.canonical,
                title = event.optString("name").ifBlank { "$away @ $home" },
                startUtc = startUtc,
                status = detail,
                state = state,
                home = home,
                away = away,
                homeLogo = homeLogo,
                awayLogo = awayLogo,
                broadcast = broadcast
            )
        }
        return result
    }

    private fun http(url: String): String {
        val connection = (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = CONNECT_TIMEOUT_MS
            readTimeout = READ_TIMEOUT_MS
            instanceFollowRedirects = true
            setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/136.0 Mobile Safari/537.36")
            setRequestProperty("Accept", "application/json")
        }
        try {
            if (connection.responseCode !in 200..299) return ""
            return connection.inputStream.bufferedReader().use { it.readText() }
        } finally {
            connection.disconnect()
        }
    }

    private fun key(event: SportsEvent): String = listOf(
        SportsScheduleService.canonicalLeagueFor(event.league),
        normalize(event.away),
        normalize(event.home),
        event.startUtc.take(16)
    ).joinToString("|")

    private fun normalize(value: String): String = value.lowercase()
        .replace(Regex("\\bfc\\b"), "")
        .replace(Regex("[^a-z0-9]+"), " ")
        .trim()
        .replace(Regex("\\s+"), " ")
}
