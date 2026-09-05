package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit

/** Reads the repository's server-refreshed canonical schedule feed. */
object CanonicalScheduleProvider {
    private const val FEED_URL = "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/android-app/data/schedule_feed.json"
    private const val OVERRIDE_URL = "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/android-app/data/schedule_overrides.json"
    private const val CONNECT_TIMEOUT_MS = 1_500
    private const val READ_TIMEOUT_MS = 4_000
    private const val OVERRIDE_READ_TIMEOUT_MS = 1_500
    private const val MAX_FEED_AGE_HOURS = 24L
    private const val UFC_PARIS_PRELIMS = "2026-09-05T16:00:00Z"
    private const val UFC_PARIS_MAIN = "2026-09-05T19:00:00Z"

    suspend fun load(league: String? = null, daysAhead: Int = 3): List<SportsEvent> = withContext(Dispatchers.IO) {
        runCatching {
            val root = JSONObject(http(cacheBustedFeedUrl()))
            if (root.optInt("schema", 0) < 4) return@runCatching emptyList()
            if (!isFresh(root.optString("generatedAt"))) return@runCatching emptyList()

            val canonical = league?.let { SportsScheduleService.canonicalLeagueFor(it) }
            val now = Instant.now()
            val cutoff = now.plus(daysAhead.toLong(), ChronoUnit.DAYS)
            val allEvents = ArrayList<JSONObject>()
            val feedEvents = root.optJSONArray("events") ?: JSONArray()
            for (i in 0 until feedEvents.length()) feedEvents.optJSONObject(i)?.let(allEvents::add)

            val overrideRoot = runCatching { JSONObject(httpOverride("$OVERRIDE_URL?ts=${System.currentTimeMillis() / 10_000L}")) }.getOrNull()
            val overridesActive = overrideRoot?.let { parseInstant(it.optString("expiresAt"))?.isAfter(now) == true } == true
            val removed = mutableSetOf<String>()
            if (overridesActive) {
                val remove = overrideRoot?.optJSONArray("remove") ?: JSONArray()
                for (i in 0 until remove.length()) {
                    val r = remove.optJSONObject(i) ?: continue
                    removed += "${r.optString("league").trim().uppercase()}|${r.optString("title").trim().lowercase()}|${r.optString("start").trim()}"
                }
                val extra = overrideRoot?.optJSONArray("events") ?: JSONArray()
                for (i in 0 until extra.length()) extra.optJSONObject(i)?.let(allEvents::add)
            }

            val out = ArrayList<SportsEvent>(allEvents.size)
            val seenIds = mutableSetOf<String>()
            for (raw in allEvents) {
                val e = canonicalizeUfc(raw) ?: continue
                val rawLeague = e.optString("league").trim()
                if (rawLeague.isBlank()) continue
                val canonicalLeague = canonicalFeedLeague(rawLeague)
                val title = e.optString("title").trim()
                val tag = e.optString("tag").uppercase()
                val isLive = tag == "LIVE"

                // Provider-authoritative LIVE events are allowed to omit a
                // scheduled start. Use the feed generation/check time as a
                // display anchor rather than silently deleting a game that the
                // server has explicitly confirmed is in progress.
                val parsedStart = parseInstant(e.optString("start"))
                val start = parsedStart ?: if (isLive) parseInstant(root.optString("generatedAt")) ?: now else continue
                val removeKey = "${rawLeague.uppercase()}|${title.lowercase()}|${start}"
                if (removeKey in removed) continue
                if (canonical != null && SportsScheduleService.canonicalLeagueFor(canonicalLeague) != canonical) continue

                if (!isLive && tag == "UPCOMING") {
                    if (start.isBefore(now.minus(26, ChronoUnit.HOURS)) || !start.isBefore(cutoff)) continue
                } else if (!isLive) {
                    if (start.isBefore(now.minus(10, ChronoUnit.MINUTES)) || !start.isBefore(cutoff)) continue
                }

                val teams = splitMatchup(title)
                val state = when (tag) { "LIVE" -> "in"; "FINAL" -> "post"; else -> "pre" }
                val status = if (tag.isNotBlank()) tag else "UPCOMING"
                val id = e.optString("id").ifBlank { "feed-${canonicalLeague}-${start}-${title}" }
                if (!seenIds.add(id)) continue
                out += SportsEvent(
                    id = id,
                    sport = sportFor(canonicalLeague), league = canonicalLeague,
                    title = title.ifBlank { "Sports event" }, startUtc = start.toString(),
                    status = status, state = state, home = e.optString("home").ifBlank { teams.second },
                    away = e.optString("away").ifBlank { teams.first },
                    homeLogo = e.optString("homeLogo").trim(), awayLogo = e.optString("awayLogo").trim(),
                    broadcast = e.optString("broadcast").trim(),
                    artUrl = e.optString("image").ifBlank { e.optString("leagueArt") }.trim(),
                    sourceUrl = e.optString("sourceUrl").trim(), youtubeVideoId = e.optString("youtubeVideoId").trim()
                )
            }
            out.sortedWith(compareBy<SportsEvent> { !(it.isLive || it.isPregame()) }.thenBy { it.startUtc })
        }.getOrDefault(emptyList())
    }

    private fun canonicalizeUfc(raw: JSONObject): JSONObject? {
        val e = JSONObject(raw.toString())
        if (!e.optString("league").trim().equals("UFC", ignoreCase = true)) return e
        val title = e.optString("title").trim()
        val low = title.lowercase()
        if (!low.contains("hooker") || !low.contains("parnasse")) return e
        if (low.contains("early prelim")) return null
        if (low.contains("main card")) {
            e.put("title", "UFC Fight Night: Hooker vs Parnasse — Main Card")
            e.put("start", UFC_PARIS_MAIN); e.put("startUtc", UFC_PARIS_MAIN)
            e.put("session", "Main Card"); if (e.optString("broadcast").isBlank()) e.put("broadcast", "Paramount+")
            return e
        }
        if (low.contains("prelims")) {
            e.put("title", "UFC Fight Night: Hooker vs Parnasse — Prelims")
            e.put("start", UFC_PARIS_PRELIMS); e.put("startUtc", UFC_PARIS_PRELIMS)
            e.put("session", "Prelims"); if (e.optString("broadcast").isBlank()) e.put("broadcast", "Paramount+")
            return e
        }
        return null
    }

    private fun cacheBustedFeedUrl(): String = "$FEED_URL?ts=${System.currentTimeMillis() / 10_000L}"

    private fun canonicalFeedLeague(label: String): String = when (label.trim().uppercase()) {
        "NCAA MEN'S SOCCER", "NCAA MEN SOCCER" -> "NCAA MEN SOCCER"
        "NCAA WOMEN'S SOCCER", "NCAA WOMEN SOCCER" -> "NCAA WOMEN SOCCER"
        "NCAA MEN'S VOLLEYBALL", "NCAA WOMEN'S VOLLEYBALL", "NCAA VB" -> "NCAA VB"
        "NCAA MEN'S BASKETBALL" -> "NCAA BB"
        "NCAA WOMEN'S BASKETBALL" -> "NCAA WBB"
        "NCAA BASEBALL" -> "NCAA BASEBALL"
        "NCAA SOFTBALL" -> "NCAA SOFTBALL"
        "NCAA MEN'S HOCKEY" -> "NCAA MEN HOCKEY"
        "NCAA WOMEN'S HOCKEY" -> "NCAA WOMEN HOCKEY"
        "NCAA MEN'S LACROSSE" -> "NCAA MEN LAX"
        "NCAA WOMEN'S LACROSSE" -> "NCAA WOMEN LAX"
        else -> label.trim()
    }

    private fun splitMatchup(title: String): Pair<String, String> {
        Regex("^(.+?)\\s+@\\s+(.+)$").find(title)?.let { return it.groupValues[1].trim() to it.groupValues[2].trim() }
        Regex("^(.+?)\\s+(?:vs\\.?|versus)\\s+(.+)$", RegexOption.IGNORE_CASE).find(title)?.let { return it.groupValues[1].trim() to it.groupValues[2].trim() }
        return "" to title.trim()
    }

    private fun sportFor(league: String): String = when {
        league.contains("NFL") || league.contains("FOOTBALL") -> "Football"
        league.contains("NBA") || league.contains("WNBA") || league.contains("BASKETBALL") -> "Basketball"
        league.contains("MLB") || league.contains("BASEBALL") -> "Baseball"
        league.contains("NHL") || league.contains("HOCKEY") -> "Hockey"
        league.contains("SOCCER") || league in setOf("MLS", "EPL", "LALIGA", "BUNDESLIGA", "SERIE A", "LIGUE 1", "UCL", "UEL", "NWSL") -> "Soccer"
        league.contains("VOLLEY") -> "Volleyball"
        league.contains("LACROSSE") || league.contains("LAX") -> "Lacrosse"
        league.contains("GOLF") || league in setOf("PGA", "LPGA", "LIV GOLF") -> "Golf"
        league.contains("TENNIS") || league in setOf("ATP", "WTA") -> "Tennis"
        league == "UFC" -> "MMA"
        else -> league
    }

    private fun parseInstant(value: String): Instant? {
        val v = value.trim()
        if (v.isBlank()) return null
        runCatching { return Instant.parse(v) }
        runCatching { return java.time.OffsetDateTime.parse(v, DateTimeFormatter.ofPattern("MM/dd/yyyy'T'HH:mm:ssX")).toInstant() }
        runCatching { return java.time.LocalDateTime.parse(v, DateTimeFormatter.ISO_LOCAL_DATE_TIME).atZone(ZoneId.of("UTC")).toInstant() }
        return null
    }

    private fun isFresh(generatedAt: String): Boolean {
        val parsed = parseInstant(generatedAt) ?: return false
        return !parsed.isBefore(Instant.now().minus(MAX_FEED_AGE_HOURS, ChronoUnit.HOURS))
    }

    private fun http(target: String): String {
        val c = URL(target).openConnection() as HttpURLConnection
        c.connectTimeout = CONNECT_TIMEOUT_MS; c.readTimeout = READ_TIMEOUT_MS; c.requestMethod = "GET"; c.instanceFollowRedirects = true; c.useCaches = false
        c.setRequestProperty("Accept", "application/json"); c.setRequestProperty("Cache-Control", "no-cache, no-store, max-age=0"); c.setRequestProperty("Pragma", "no-cache"); c.setRequestProperty("User-Agent", "XSportsX/2.0 Android")
        return try { if (c.responseCode !in 200..299) error("Schedule feed HTTP ${c.responseCode}"); c.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() } } finally { c.disconnect() }
    }

    private fun httpOverride(target: String): String {
        val c = URL(target).openConnection() as HttpURLConnection
        c.connectTimeout = 800; c.readTimeout = OVERRIDE_READ_TIMEOUT_MS; c.requestMethod = "GET"; c.instanceFollowRedirects = true; c.useCaches = false
        c.setRequestProperty("Accept", "application/json"); c.setRequestProperty("Cache-Control", "no-cache, no-store, max-age=0")
        return try { if (c.responseCode !in 200..299) error("Schedule override HTTP ${c.responseCode}"); c.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() } } finally { c.disconnect() }
    }
}
