package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URLEncoder
import java.net.URL

/** Lightweight event discovery. It resolves an event first, then lets the
 * existing StreamResolver search the user's/private and public sources. */
data class SportsEvent(
    val id: String,
    val sport: String,
    val league: String,
    val name: String,
    val shortName: String,
    val startTime: String,
    val status: String,
    val home: String = "",
    val away: String = "",
    val logoUrl: String = ""
)

data class EventSearchResult(val event: SportsEvent, val score: Int)

class EventFinder {
    private data class Endpoint(val sport: String, val league: String)

    private val endpoints = listOf(
        Endpoint("football", "nfl"), Endpoint("basketball", "nba"),
        Endpoint("baseball", "mlb"), Endpoint("hockey", "nhl"),
        Endpoint("soccer", "usa.1"), Endpoint("soccer", "eng.1"),
        Endpoint("soccer", "esp.1"), Endpoint("soccer", "uefa.champions"),
        Endpoint("mma", "ufc"), Endpoint("boxing", "boxing"),
        Endpoint("volleyball", "ncaa-womens-volleyball"),
        Endpoint("racing", "f1")
    )

    suspend fun search(query: String, maxResults: Int = 20): List<EventSearchResult> = withContext(Dispatchers.IO) {
        val q = normalize(query)
        if (q.length < 2) return@withContext emptyList()
        val results = ArrayList<EventSearchResult>()
        for (endpoint in endpoints) {
            val events = fetch(endpoint)
            for (event in events) {
                val score = score(q, event)
                if (score > 0) results += EventSearchResult(event, score)
            }
        }
        results.sortedWith(compareByDescending<EventSearchResult> { it.score }.thenBy { it.event.startTime }).distinctBy { it.event.id }.take(maxResults)
    }

    /** Useful for searches such as "UFC Fight Night", "Fight Night" or a
     * specific fighter/event title. */
    suspend fun searchUfcFightNight(query: String = "UFC Fight Night", maxResults: Int = 20): List<EventSearchResult> =
        withContext(Dispatchers.IO) {
            val q = normalize(query)
            fetch(Endpoint("mma", "ufc")).mapNotNull { event ->
                val s = score(q, event)
                if (s > 0 || (q.contains("fight night") && normalize(event.name).contains("fight night"))) EventSearchResult(event, maxOf(s, 100)) else null
            }.sortedByDescending { it.score }.take(maxResults)
        }

    private fun fetch(endpoint: Endpoint): List<SportsEvent> = runCatching {
        val url = "https://site.api.espn.com/apis/site/v2/sports/${endpoint.sport}/${endpoint.league}/scoreboard?limit=100"
        val json = JSONObject(http(url))
        val events = json.optJSONArray("events") ?: JSONArray()
        buildList {
            for (i in 0 until events.length()) {
                val event = events.optJSONObject(i) ?: continue
                val competition = event.optJSONArray("competitions")?.optJSONObject(0)
                val competitors = competition?.optJSONArray("competitors") ?: JSONArray()
                val away = competitorName(competitors, "away")
                val home = competitorName(competitors, "home")
                val name = event.optString("name").ifBlank { event.optString("shortName") }
                val status = event.optJSONObject("status")?.optJSONObject("type")?.optString("name").orEmpty()
                val logo = event.optJSONArray("competitions")?.optJSONObject(0)?.optJSONArray("competitors")?.optJSONObject(0)?.optJSONArray("logos")?.optJSONObject(0)?.optString("href").orEmpty()
                add(SportsEvent(event.optString("id"), endpoint.sport, endpoint.league, name, event.optString("shortName"), event.optString("date"), status, home, away, logo))
            }
        }
    }.getOrDefault(emptyList())

    private fun competitorName(array: JSONArray, homeAway: String): String {
        for (i in 0 until array.length()) {
            val c = array.optJSONObject(i) ?: continue
            if (c.optString("homeAway").equals(homeAway, true)) {
                val team = c.optJSONObject("team")
                return team?.optString("displayName").orEmpty().ifBlank { team?.optString("shortDisplayName").orEmpty() }
            }
        }
        return ""
    }

    private fun score(q: String, event: SportsEvent): Int {
        val fields = listOf(event.name, event.shortName, event.home, event.away, event.league)
            .map(::normalize)
        if (fields.any { it == q }) return 100
        if (fields.any { it.contains(q) }) return 90
        val tokens = q.split(' ').filter { it.length >= 3 }
        if (tokens.isEmpty()) return 0
        val hits = tokens.count { token -> fields.any { it.contains(token) } }
        return when {
            hits == tokens.size -> 80
            hits >= 2 -> 55
            hits == 1 && tokens.size == 1 -> 45
            else -> 0
        }
    }

    private fun normalize(value: String): String = value.lowercase()
        .replace("’", "'").replace(Regex("[^a-z0-9]+"), " ").trim().replace(Regex("\\s+"), " ")

    private fun http(target: String): String {
        val c = (URL(target).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"; connectTimeout = 4000; readTimeout = 8000; instanceFollowRedirects = true
            setRequestProperty("User-Agent", "XSportsX-EventFinder/1.0")
            setRequestProperty("Accept", "application/json")
        }
        return try {
            if (c.responseCode !in 200..299) error("HTTP ${c.responseCode}")
            c.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        } finally { c.disconnect() }
    }
}
