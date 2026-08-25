package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale

data class SportsEvent(
    val id: String, val sport: String, val league: String, val title: String,
    val startUtc: String, val status: String, val state: String,
    val home: String, val away: String, val homeLogo: String, val awayLogo: String,
    val broadcast: String, val artUrl: String = "", val sourceUrl: String = ""
) {
    val isLive: Boolean get() = state == "in" || state == "live"
    val isUpcoming: Boolean get() = state == "pre" || state == "scheduled"
    val searchText: String get() = listOf(home, away, title, league, broadcast).joinToString(" ")
}

data class ScheduleLeague(val sport: String, val league: String, val path: String)

private data class OfficialEvent(
    val id: String, val title: String, val startUtc: String, val status: String,
    val state: String, val artUrl: String, val sourceUrl: String, val league: String
)

object SportsScheduleService {
    private val leagues = listOf(
        ScheduleLeague("Football", "NFL", "football/nfl"),
        ScheduleLeague("College Football", "NCAA", "football/college-football"),
        ScheduleLeague("Basketball", "NBA", "basketball/nba"),
        ScheduleLeague("Basketball", "WNBA", "basketball/wnba"),
        ScheduleLeague("College Basketball", "NCAA", "basketball/mens-college-basketball"),
        ScheduleLeague("Baseball", "MLB", "baseball/mlb"),
        ScheduleLeague("Hockey", "NHL", "hockey/nhl"),
        ScheduleLeague("Soccer", "MLS", "soccer/usa.1"),
        ScheduleLeague("Soccer", "EPL", "soccer/eng.1"),
        ScheduleLeague("Soccer", "LaLiga", "soccer/esp.1"),
        ScheduleLeague("Soccer", "Bundesliga", "soccer/ger.1"),
        ScheduleLeague("Soccer", "Serie A", "soccer/ita.1"),
        ScheduleLeague("Soccer", "Ligue 1", "soccer/fra.1"),
        ScheduleLeague("Soccer", "UCL", "soccer/uefa.champions"),
        ScheduleLeague("Soccer", "UEL", "soccer/uefa.europa"),
        ScheduleLeague("Soccer", "NWSL", "soccer/usa.nwsl"),
        ScheduleLeague("Racing", "F1", "racing/f1")
    )

    suspend fun load(): List<SportsEvent> = withContext(Dispatchers.IO) {
        val today = LocalDate.now(ZoneOffset.UTC)
        val end = today.plusDays(14)
        val dates = "${today.format(DateTimeFormatter.BASIC_ISO_DATE)}-${end.format(DateTimeFormatter.BASIC_ISO_DATE)}"
        val espn = coroutineScope {
            leagues.map { league -> async { runCatching { fetchLeague(league, dates) }.getOrDefault(emptyList()) } }
                .awaitAll().flatten()
        }
        val officialCombat = coroutineScope {
            listOf(
                async { runCatching { fetchOfficialCombat("UFC", "https://www.ufc.com/events") }.getOrDefault(emptyList()) },
                async { runCatching { fetchOfficialCombat("DWCS", "https://www.ufc.com/dwcs") }.getOrDefault(emptyList()) },
                async { runCatching { fetchOfficialCombat("Boxing", "https://toprank.com/events") }.getOrDefault(emptyList()) },
                async { runCatching { fetchOfficialCombat("Boxing", "https://www.premierboxingchampions.com/schedule") }.getOrDefault(emptyList()) }
            ).awaitAll().flatten()
        }
        (espn + officialCombat.map { it.toSportsEvent() })
            .distinctBy { it.id.ifBlank { it.title + it.startUtc + it.league } }
            .filter { it.isLive || it.isUpcoming }
            .sortedWith(compareBy<SportsEvent> { !it.isLive }.thenBy { it.startUtc })
    }

    private fun fetchLeague(league: ScheduleLeague, dates: String): List<SportsEvent> {
        val url = "https://site.api.espn.com/apis/site/v2/sports/${league.path}/scoreboard?dates=$dates&limit=500"
        val root = JSONObject(http(url))
        val events = root.optJSONArray("events") ?: return emptyList()
        val out = ArrayList<SportsEvent>(events.length())
        for (i in 0 until events.length()) {
            val e = events.optJSONObject(i) ?: continue
            val competition = e.optJSONArray("competitions")?.optJSONObject(0) ?: continue
            val competitors = competition.optJSONArray("competitors") ?: continue
            var home = ""; var away = ""; var homeLogo = ""; var awayLogo = ""
            for (j in 0 until competitors.length()) {
                val c = competitors.optJSONObject(j) ?: continue
                val team = c.optJSONObject("team") ?: continue
                val name = team.optString("displayName").ifBlank { team.optString("shortDisplayName") }
                val logo = team.optString("logo")
                if (c.optString("homeAway") == "home") { home = name; homeLogo = logo } else { away = name; awayLogo = logo }
            }
            val status = competition.optJSONObject("status") ?: e.optJSONObject("status") ?: JSONObject()
            val type = status.optJSONObject("type") ?: JSONObject()
            val broadcast = buildString {
                val b = competition.optJSONArray("broadcasts")
                if (b != null) for (k in 0 until b.length()) {
                    val names = b.optJSONObject(k)?.optJSONArray("names")
                    if (names != null) for (n in 0 until names.length()) {
                        if (isNotEmpty()) append(" • ")
                        append(names.optString(n))
                    }
                }
                if (isEmpty()) append(competition.optString("broadcast"))
            }
            out += SportsEvent(
                id = e.optString("id"), sport = league.sport, league = league.league,
                title = e.optString("name").ifBlank { e.optString("shortName") },
                startUtc = e.optString("date").ifBlank { competition.optString("startDate") },
                status = type.optString("shortDetail").ifBlank { type.optString("detail") },
                state = type.optString("state"), home = home, away = away,
                homeLogo = homeLogo, awayLogo = awayLogo, broadcast = broadcast,
                artUrl = e.optString("image")
            )
        }
        return out
    }

    private fun fetchOfficialCombat(kind: String, pageUrl: String): List<OfficialEvent> {
        val html = http(pageUrl, "text/html,application/xhtml+xml")
        val scripts = Regex(
            "<script[^>]+type=[\\\"']application/ld\\+json[\\\"'][^>]*>(.*?)</script>",
            setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL)
        )
        val out = ArrayList<OfficialEvent>()
        for (match in scripts.findAll(html)) {
            val raw = match.groupValues[1].trim()
            val root: Any = runCatching { JSONObject(raw) }.getOrNull()
                ?: runCatching { JSONArray(raw) }.getOrNull() ?: continue
            collectJsonLd(root, kind, pageUrl, out)
        }
        return out.distinctBy { it.id.ifBlank { it.title + it.startUtc } }
    }

    private fun collectJsonLd(value: Any, kind: String, pageUrl: String, out: MutableList<OfficialEvent>) {
        when (value) {
            is JSONArray -> for (i in 0 until value.length()) collectJsonLd(value.opt(i), kind, pageUrl, out)
            is JSONObject -> {
                value.opt("@graph")?.let { collectJsonLd(it, kind, pageUrl, out) }
                val type = value.optString("@type").lowercase(Locale.US)
                if (type.contains("event")) {
                    val name = value.optString("name").trim()
                    val date = value.optString("startDate").ifBlank { value.optString("startTime") }
                    if (name.isNotBlank() && date.isNotBlank()) {
                        val url = value.optString("url").ifBlank { pageUrl }
                        val image = when (val image = value.opt("image")) {
                            is JSONArray -> image.optString(0)
                            else -> image?.toString().orEmpty()
                        }
                        val state = runCatching { if (Instant.parse(date).isAfter(Instant.now())) "pre" else "in" }.getOrDefault("pre")
                        out += OfficialEvent(
                            id = value.optString("@id").ifBlank { url + "#" + name }, title = name,
                            startUtc = date, status = value.optString("eventStatus"), state = state,
                            artUrl = image, sourceUrl = url, league = kind
                        )
                    }
                }
            }
        }
    }

    private fun OfficialEvent.toSportsEvent() = SportsEvent(
        id = id, sport = if (league == "Boxing") "Combat" else "MMA", league = league,
        title = title, startUtc = startUtc, status = status, state = state,
        home = "", away = "", homeLogo = "", awayLogo = "", broadcast = "",
        artUrl = artUrl, sourceUrl = sourceUrl
    )

    private fun http(target: String, accept: String = "application/json"): String {
        val c = (URL(target).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"; connectTimeout = 9000; readTimeout = 15000
            instanceFollowRedirects = true
            setRequestProperty("User-Agent", "XSportsX/1.0")
            setRequestProperty("Accept", accept)
        }
        return try {
            val code = c.responseCode
            if (code !in 200..299) error("Schedule HTTP $code")
            c.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        } finally { c.disconnect() }
    }
}
