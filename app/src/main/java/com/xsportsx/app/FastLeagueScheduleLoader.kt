package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter

/** Fast, bounded league-screen loader using one scoreboard request per selected league. */
object FastLeagueScheduleLoader {
    private const val TIMEOUT_MS = 6_000L
    private const val CONNECT_TIMEOUT_MS = 1_500
    private val bases = listOf(
        "https://site.api.espn.com/apis/site/v2",
        "https://site.web.api.espn.com/apis/site/v2"
    )

    private data class Endpoint(val sport: String, val path: String, val query: String = "")

    private fun endpoint(league: String): Endpoint? = when (SportsScheduleService.canonicalLeagueFor(league)) {
        "NFL" -> Endpoint("football", "nfl")
        "NBA" -> Endpoint("basketball", "nba")
        "WNBA" -> Endpoint("basketball", "wnba")
        "NCAA FB" -> Endpoint("football", "college-football", "groups=80")
        "NCAA FCS" -> Endpoint("football", "college-football", "groups=81")
        "NCAA BB" -> Endpoint("basketball", "mens-college-basketball")
        "NCAA WBB" -> Endpoint("basketball", "womens-college-basketball")
        "MLB" -> Endpoint("baseball", "mlb")
        "NCAA BASEBALL" -> Endpoint("baseball", "college-baseball")
        "NHL" -> Endpoint("hockey", "nhl")
        "NCAA VB" -> Endpoint("volleyball", "womens-college-volleyball")
        "NCAA MEN SOCCER" -> Endpoint("soccer", "usa.ncaa.m.1")
        "NCAA WOMEN SOCCER" -> Endpoint("soccer", "usa.ncaa.w.1")
        "MLS" -> Endpoint("soccer", "usa.1")
        "EPL" -> Endpoint("soccer", "eng.1")
        "LALIGA" -> Endpoint("soccer", "esp.1")
        "BUNDESLIGA" -> Endpoint("soccer", "ger.1")
        "SERIE A" -> Endpoint("soccer", "ita.1")
        "LIGUE 1" -> Endpoint("soccer", "fra.1")
        "UCL" -> Endpoint("soccer", "uefa.champions")
        "UEL" -> Endpoint("soccer", "uefa.europa")
        "NWSL" -> Endpoint("soccer", "usa.nwsl")
        "UFC" -> Endpoint("mma", "ufc")
        "BOXING" -> Endpoint("boxing", "boxing")
        else -> null
    }

    suspend fun load(league: String, daysAhead: Int = 3): List<SportsEvent> = withContext(Dispatchers.IO) {
        val canonical = SportsScheduleService.canonicalLeagueFor(league)
        val ep = endpoint(canonical) ?: return@withContext emptyList()
        val today = LocalDate.now(ZoneId.systemDefault())
        val end = today.plusDays(daysAhead.toLong())
        val dates = "${today.format(DateTimeFormatter.BASIC_ISO_DATE)}-${end.format(DateTimeFormatter.BASIC_ISO_DATE)}"
        val suffix = buildString {
            append("/sports/${ep.sport}/${ep.path}/scoreboard?dates=$dates&limit=1000")
            if (ep.query.isNotBlank()) append('&').append(ep.query)
        }
        for (base in bases) {
            val result = withTimeoutOrNull(TIMEOUT_MS) {
                runCatching { parse(JSONObject(get("$base$suffix")), ep, canonical) }.getOrDefault(emptyList())
            }.orEmpty()
            if (result.isNotEmpty()) return@withContext result
        }
        emptyList()
    }

    private fun get(target: String): String {
        val c = URL(target).openConnection() as HttpURLConnection
        c.connectTimeout = CONNECT_TIMEOUT_MS
        c.readTimeout = TIMEOUT_MS.toInt()
        c.requestMethod = "GET"
        c.instanceFollowRedirects = true
        c.setRequestProperty("User-Agent", "XSportsX/1.9 Android")
        c.setRequestProperty("Accept", "application/json")
        c.setRequestProperty("Referer", "https://www.espn.com/")
        return try {
            if (c.responseCode !in 200..299) error("HTTP ${c.responseCode}")
            c.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        } finally { c.disconnect() }
    }

    private fun parse(root: JSONObject, ep: Endpoint, canonical: String): List<SportsEvent> {
        val events = root.optJSONArray("events") ?: return emptyList()
        val out = ArrayList<SportsEvent>(events.length())
        for (i in 0 until events.length()) {
            val e = events.optJSONObject(i) ?: continue
            val comp = e.optJSONArray("competitions")?.optJSONObject(0) ?: continue
            val teams = comp.optJSONArray("competitors") ?: continue
            var home = ""; var away = ""; var homeLogo = ""; var awayLogo = ""
            for (j in 0 until teams.length()) {
                val c = teams.optJSONObject(j) ?: continue
                val t = c.optJSONObject("team")
                val name = t?.optString("displayName")?.ifBlank { t.optString("shortDisplayName") }
                    ?.ifBlank { c.optString("displayName") }.orEmpty()
                val logo = t?.optString("logo").orEmpty()
                if (c.optString("homeAway").equals("home", true)) { home = name; homeLogo = logo }
                else { away = name; awayLogo = logo }
            }
            val status = comp.optJSONObject("status") ?: e.optJSONObject("status") ?: JSONObject()
            val type = status.optJSONObject("type") ?: JSONObject()
            val state = type.optString("state").ifBlank { status.optString("state") }
            val detail = type.optString("shortDetail").ifBlank { type.optString("detail") }.ifBlank { type.optString("name") }
            val start = e.optString("date").ifBlank { comp.optString("startDate") }
            if (start.isBlank() || home.isBlank() || away.isBlank()) continue
            val broadcasts = comp.optJSONArray("broadcasts")
            val broadcast = buildString {
                if (broadcasts != null) for (j in 0 until broadcasts.length()) {
                    val names = broadcasts.optJSONObject(j)?.optJSONArray("names") ?: continue
                    for (k in 0 until names.length()) {
                        val n = names.optString(k)
                        if (n.isNotBlank()) { if (isNotEmpty()) append(", "); append(n) }
                    }
                }
            }
            val title = e.optString("name").ifBlank { "$away vs $home" }
            out += SportsEvent(e.optString("id"), ep.sport, canonical, title, start, detail, state, home, away, homeLogo, awayLogo, broadcast, e.optString("image"), "", "")
        }
        return out.distinctBy { it.id.ifBlank { "${it.league}|${it.away}|${it.home}|${it.startUtc.take(16)}" } }
            .sortedBy { it.startUtc }
    }
}
