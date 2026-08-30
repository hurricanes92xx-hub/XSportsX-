package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.LocalDate
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

/**
 * Lightweight secondary schedule source. It is only consulted when the primary
 * ESPN feeds return no events, so it cannot slow the normal schedule path.
 * TheSportsDB free v1 API supports broad sports/league/day coverage.
 */
object ScheduleFallbackProvider {
    private const val BASE = "https://www.thesportsdb.com/api/v1/json/123"
    private const val CONNECT_TIMEOUT_MS = 1200
    private const val READ_TIMEOUT_MS = 2500
    private val dateFormatter = DateTimeFormatter.ISO_LOCAL_DATE

    suspend fun fetch(
        league: String,
        sport: String,
        start: LocalDate,
        end: LocalDate
    ): List<SportsEvent> = withContext(Dispatchers.IO) {
        val out = ArrayList<SportsEvent>()
        var day = start
        while (!day.isAfter(end)) {
            val result = runCatching { fetchDay(day, sport, league) }.getOrDefault(emptyList())
            out += result
            if (out.size >= 150) break
            day = day.plusDays(1)
        }
        out.distinctBy { it.id.ifBlank { listOf(it.league, norm(it.home), norm(it.away), it.startUtc.take(16)).joinToString("|") } }
    }

    private fun fetchDay(day: LocalDate, sport: String, league: String): List<SportsEvent> {
        val target = "$BASE/eventsday.php?d=${day.format(dateFormatter)}"
        val root = JSONObject(http(target))
        val events = root.optJSONArray("events") ?: JSONArray()
        val wantedSport = norm(sport)
        val wantedLeague = norm(league)
        val out = ArrayList<SportsEvent>()
        for (i in 0 until events.length()) {
            val e = events.optJSONObject(i) ?: continue
            val eventSport = e.optString("strSport")
            val eventLeague = e.optString("strLeague")
            if (wantedSport.isNotBlank() && norm(eventSport).isNotBlank() && !norm(eventSport).contains(wantedSport) && !wantedSport.contains(norm(eventSport))) continue
            if (wantedLeague.isNotBlank() && norm(eventLeague).isNotBlank() && !norm(eventLeague).contains(wantedLeague) && !wantedLeague.contains(norm(eventLeague))) continue
            val home = e.optString("strHomeTeam").trim()
            val away = e.optString("strAwayTeam").trim()
            if (home.isBlank() || away.isBlank()) continue
            val date = e.optString("dateEvent").trim()
            val time = e.optString("strTime").trim().ifBlank { "00:00:00" }.let { if (it.length == 5) "$it:00" else it }
            val startUtc = runCatching {
                LocalDate.parse(date).atTime(java.time.LocalTime.parse(time.take(8))).atOffset(ZoneOffset.UTC).toInstant().toString()
            }.getOrElse { "${date}T00:00:00Z" }
            val canonicalLeague = eventLeague.ifBlank { league }.trim()
            out += SportsEvent(
                id = "tsdb-${e.optString("idEvent").ifBlank { "$date-${norm(away)}-${norm(home)}" }}",
                sport = sport,
                league = canonicalLeague,
                title = e.optString("strEvent").ifBlank { "$away vs $home" },
                startUtc = startUtc,
                status = e.optString("strStatus"),
                state = "",
                home = home,
                away = away,
                homeLogo = e.optString("strHomeTeamBadge"),
                awayLogo = e.optString("strAwayTeamBadge"),
                broadcast = e.optString("strTVStation"),
                artUrl = e.optString("strThumb"),
                sourceUrl = "https://www.thesportsdb.com/"
            )
        }
        return out
    }

    private fun http(target: String): String {
        val c = URL(target).openConnection() as HttpURLConnection
        c.connectTimeout = CONNECT_TIMEOUT_MS
        c.readTimeout = READ_TIMEOUT_MS
        c.requestMethod = "GET"
        c.setRequestProperty("Accept", "application/json")
        c.setRequestProperty("User-Agent", "XSportsX/1.0 Android")
        return try {
            check(c.responseCode in 200..299)
            c.inputStream.bufferedReader().use { it.readText() }
        } finally {
            c.disconnect()
        }
    }

    private fun norm(value: String): String = value.lowercase().replace(Regex("[^a-z0-9]+"), " ").trim().replace(Regex("\\s+"), " ")
}
