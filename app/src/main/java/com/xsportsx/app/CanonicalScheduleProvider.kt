package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException
import java.time.temporal.ChronoUnit

/**
 * Reads the repository's server-refreshed canonical schedule feed.
 * Mobile and TV use this same feed before falling back to direct providers.
 */
object CanonicalScheduleProvider {
    private const val FEED_URL = "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/android-app/data/schedule_feed.json"
    private const val CONNECT_TIMEOUT_MS = 1_500
    private const val READ_TIMEOUT_MS = 4_000
    private const val MAX_FEED_AGE_HOURS = 24L

    suspend fun load(league: String? = null, daysAhead: Int = 3): List<SportsEvent> = withContext(Dispatchers.IO) {
        runCatching {
            val root = JSONObject(http(FEED_URL))
            if (root.optInt("schema", 0) < 4) return@runCatching emptyList()
            if (!isFresh(root.optString("generatedAt"))) return@runCatching emptyList()

            val canonical = league?.let { SportsScheduleService.canonicalLeagueFor(it) }
            val now = Instant.now()
            val cutoff = now.plus(daysAhead.toLong(), ChronoUnit.DAYS)
            val events = root.optJSONArray("events") ?: JSONArray()
            val out = ArrayList<SportsEvent>(events.length())

            for (i in 0 until events.length()) {
                val e = events.optJSONObject(i) ?: continue
                val rawLeague = e.optString("league").trim()
                if (rawLeague.isBlank()) continue
                if (canonical != null && SportsScheduleService.canonicalLeagueFor(rawLeague) != canonical) continue

                val start = parseInstant(e.optString("start")) ?: continue
                if (start.isBefore(now.minus(10, ChronoUnit.MINUTES)) || !start.isBefore(cutoff)) continue

                val title = e.optString("title").trim()
                val teams = splitMatchup(title)
                val tag = e.optString("tag").uppercase()
                val state = when (tag) {
                    "LIVE" -> "in"
                    "FINAL" -> "post"
                    else -> "pre"
                }
                val status = if (tag.isNotBlank()) tag else "UPCOMING"
                val canonicalLeague = SportsScheduleService.canonicalLeagueFor(rawLeague)

                out += SportsEvent(
                    id = e.optString("id").ifBlank { "feed-${canonicalLeague}-${start}-${title}" },
                    sport = sportFor(canonicalLeague),
                    league = canonicalLeague,
                    title = title.ifBlank { "Sports event" },
                    startUtc = start.toString(),
                    status = status,
                    state = state,
                    home = teams.second,
                    away = teams.first,
                    homeLogo = "",
                    awayLogo = "",
                    broadcast = e.optString("broadcast").trim(),
                    artUrl = e.optString("image").trim(),
                    sourceUrl = e.optString("sourceUrl").trim(),
                    youtubeId = ""
                )
            }

            out.distinctBy { it.id.ifBlank { "${it.league}|${it.away}|${it.home}|${it.startUtc.take(16)}" } }
                .sortedWith(compareBy<SportsEvent> { !(it.isLive || it.isPregame()) }.thenBy { it.startUtc })
        }.getOrDefault(emptyList())
    }

    private fun splitMatchup(title: String): Pair<String, String> {
        val at = Regex("^(.+?)\\s+@\\s+(.+)$").find(title)
        if (at != null) return at.groupValues[1].trim() to at.groupValues[2].trim()
        val vs = Regex("^(.+?)\\s+(?:vs\\.?|versus)\\s+(.+)$", RegexOption.IGNORE_CASE).find(title)
        if (vs != null) return vs.groupValues[1].trim() to vs.groupValues[2].trim()
        return "" to title.trim()
    }

    private fun sportFor(league: String): String = when {
        league.contains("NFL") || league.contains("FOOTBALL") -> "Football"
        league.contains("NBA") || league.contains("WNBA") || league.contains("BASKETBALL") -> "Basketball"
        league.contains("MLB") || league.contains("BASEBALL") -> "Baseball"
        league.contains("NHL") || league.contains("HOCKEY") -> "Hockey"
        league.contains("SOCCER") || league in setOf("MLS", "EPL", "LALIGA", "BUNDESLIGA", "SERIE A", "LIGUE 1", "UCL", "UEL", "NWSL") -> "Soccer"
        league.contains("VOLLEY") -> "Volleyball"
        league.contains("LACROSSE") -> "Lacrosse"
        league.contains("GOLF") || league in setOf("PGA", "LPGA", "LIV GOLF") -> "Golf"
        league.contains("TENNIS") || league in setOf("ATP", "WTA") -> "Tennis"
        league == "UFC" -> "MMA"
        else -> league
    }

    private fun parseInstant(value: String): Instant? {
        val v = value.trim()
        if (v.isBlank()) return null
        runCatching { return Instant.parse(v) }
        runCatching {
            return java.time.OffsetDateTime.parse(v, DateTimeFormatter.ofPattern("MM/dd/yyyy'T'HH:mm:ssX")).toInstant()
        }
        runCatching {
            return java.time.LocalDateTime.parse(v, DateTimeFormatter.ISO_LOCAL_DATE_TIME).atZone(ZoneId.of("UTC")).toInstant()
        }
        return null
    }

    private fun isFresh(generatedAt: String): Boolean {
        val parsed = parseInstant(generatedAt) ?: return false
        return !parsed.isBefore(Instant.now().minus(MAX_FEED_AGE_HOURS, ChronoUnit.HOURS))
    }

    private fun http(target: String): String {
        val c = URL(target).openConnection() as HttpURLConnection
        c.connectTimeout = CONNECT_TIMEOUT_MS
        c.readTimeout = READ_TIMEOUT_MS
        c.requestMethod = "GET"
        c.instanceFollowRedirects = true
        c.setRequestProperty("Accept", "application/json")
        c.setRequestProperty("User-Agent", "XSportsX/2.0 Android")
        return try {
            if (c.responseCode !in 200..299) error("Schedule feed HTTP ${c.responseCode}")
            c.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        } finally {
            c.disconnect()
        }
    }
}
