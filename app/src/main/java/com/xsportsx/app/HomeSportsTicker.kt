package com.xsportsx.app

import androidx.compose.foundation.background
import androidx.compose.foundation.basicMarquee
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale
import java.util.TimeZone

data class TickerItem(val kind: String, val league: String, val text: String, val timestamp: Long = 0L)
data class TickerLeague(val name: String, val sport: String, val id: String)
data class TickerLeagueGroup(val league: String, val items: List<TickerItem>)

private val tickerLeagues = listOf(
    TickerLeague("NFL", "football", "nfl"),
    TickerLeague("NCAA FB", "football", "college-football"),
    TickerLeague("NBA", "basketball", "nba"),
    TickerLeague("WNBA", "basketball", "wnba"),
    TickerLeague("NCAA BB", "basketball", "mens-college-basketball"),
    TickerLeague("MLB", "baseball", "mlb"),
    TickerLeague("NHL", "hockey", "nhl"),
    TickerLeague("MLS", "soccer", "usa.1"),
    TickerLeague("EPL", "soccer", "eng.1"),
    TickerLeague("UCL", "soccer", "uefa.champions"),
    TickerLeague("LaLiga", "soccer", "esp.1"),
    TickerLeague("Serie A", "soccer", "ita.1"),
    TickerLeague("Bundesliga", "soccer", "ger.1"),
    TickerLeague("Ligue 1", "soccer", "fra.1")
)

private fun dateRange(): String {
    val fmt = SimpleDateFormat("yyyyMMdd", Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") }
    val cal = Calendar.getInstance(TimeZone.getTimeZone("UTC"))
    cal.add(Calendar.DAY_OF_YEAR, -1)
    val yesterday = fmt.format(cal.time)
    cal.add(Calendar.DAY_OF_YEAR, 2)
    val tomorrow = fmt.format(cal.time)
    return "$yesterday-$tomorrow"
}

private fun getJson(url: String): JSONObject? {
    val connection = try { URL(url).openConnection() as HttpURLConnection } catch (_: Exception) { return null }
    return try {
        connection.connectTimeout = 3500
        connection.readTimeout = 5500
        connection.requestMethod = "GET"
        connection.setRequestProperty("User-Agent", "XSportsX/1.6")
        connection.setRequestProperty("Accept", "application/json")
        if (connection.responseCode !in 200..299) null
        else connection.inputStream.bufferedReader().use { JSONObject(it.readText()) }
    } catch (_: Exception) {
        null
    } finally {
        connection.disconnect()
    }
}

private fun eventTime(event: JSONObject): Long {
    val raw = event.optString("date", "")
    return try { java.time.Instant.parse(raw).toEpochMilli() } catch (_: Exception) { 0L }
}

private fun tickerPriority(kind: String): Int = when (kind) {
    "LIVE" -> 0
    "UPCOMING" -> 1
    "FINAL" -> 2
    "NEWS" -> 3
    else -> 4
}

private suspend fun loadLeague(league: TickerLeague): TickerLeagueGroup = withContext(Dispatchers.IO) {
    val url = "https://site.api.espn.com/apis/site/v2/sports/${league.sport}/${league.id}/scoreboard?dates=${dateRange()}&limit=50"
    val json = getJson(url)
    val events = json?.optJSONArray("events")
    val now = System.currentTimeMillis()
    val cutoff = now - 24L * 60L * 60L * 1000L
    val items = buildList {
        if (events != null) {
            for (i in 0 until events.length()) {
                val event = events.optJSONObject(i) ?: continue
                val competition = event.optJSONArray("competitions")?.optJSONObject(0) ?: continue
                val competitors = competition.optJSONArray("competitors") ?: continue
                var home = "TBD"
                var away = "TBD"
                var homeScore = ""
                var awayScore = ""

                for (j in 0 until competitors.length()) {
                    val team = competitors.optJSONObject(j) ?: continue
                    val teamObj = team.optJSONObject("team")
                    val name = teamObj?.optString("abbreviation")?.ifBlank { teamObj.optString("shortDisplayName") }
                        .orEmpty().ifBlank { "TBD" }
                    val score = team.optString("score")
                    if (team.optString("homeAway") == "home") {
                        home = name
                        homeScore = score
                    } else {
                        away = name
                        awayScore = score
                    }
                }

                val statusType = competition.optJSONObject("status")?.optJSONObject("type")
                val state = statusType?.optString("state").orEmpty().ifBlank { "pre" }
                val detail = statusType?.optString("shortDetail").orEmpty()
                val timestamp = eventTime(event)
                val kind = when (state) {
                    "in" -> "LIVE"
                    "post" -> if (timestamp == 0L || timestamp >= cutoff) "FINAL" else "EXPIRED"
                    else -> "UPCOMING"
                }
                if (kind == "EXPIRED") continue

                val text = when (kind) {
                    "UPCOMING" -> "$away @ $home${detail.takeIf { it.isNotBlank() }?.let { " • $it" } ?: ""}"
                    else -> "$away $awayScore  •  $home $homeScore"
                }
                add(TickerItem(kind, league.name, text, timestamp))
            }
        }
    }

    TickerLeagueGroup(
        league.name,
        items.sortedWith(compareBy<TickerItem> { tickerPriority(it.kind) }.thenBy { it.timestamp }).take(10)
    )
}

private suspend fun loadBreakingNews(): TickerLeagueGroup = withContext(Dispatchers.IO) {
    val urls = listOf(
        "https://site.api.espn.com/apis/site/v2/sports/news?region=us&lang=en&limit=12",
        "https://site.api.espn.com/apis/site/v2/sports/general/news?region=us&lang=en&limit=12"
    )
    var json: JSONObject? = null
    for (url in urls) {
        json = getJson(url)
        if (json != null) break
    }

    val articles = json?.optJSONArray("articles")
    val items = buildList {
        if (articles != null) {
            for (i in 0 until articles.length()) {
                val article = articles.optJSONObject(i) ?: continue
                val headline = article.optString("headline").trim()
                if (headline.isBlank()) continue
                val published = try {
                    java.time.Instant.parse(article.optString("published")).toEpochMilli()
                } catch (_: Exception) { 0L }
                add(TickerItem("NEWS", "BREAKING", headline, published))
            }
        }
    }.sortedByDescending { it.timestamp }.take(8)

    TickerLeagueGroup("BREAKING NEWS", items)
}

private suspend fun loadTickerGroups(): List<TickerLeagueGroup> = coroutineScope {
    val leagueGroups = tickerLeagues.map { league -> async { loadLeague(league) } }.awaitAll()
    val news = async { loadBreakingNews() }.await()
    leagueGroups.filter { it.items.isNotEmpty() } + listOfNotNull(news.takeIf { it.items.isNotEmpty() })
}

private fun tickerLine(group: TickerLeagueGroup): String = group.items.joinToString("     •     ") { item ->
    "${item.kind}  ${item.text}"
}

@Composable
fun HomeSportsTicker(modifier: Modifier = Modifier) {
    var groups by remember { mutableStateOf<List<TickerLeagueGroup>>(emptyList()) }
    var activeIndex by remember { mutableIntStateOf(0) }
    var loading by remember { mutableStateOf(true) }
    var lastRefresh by remember { mutableLongStateOf(0L) }

    LaunchedEffect(Unit) {
        while (isActive) {
            loading = true
            val loaded = runCatching { loadTickerGroups() }.getOrDefault(emptyList())
            if (loaded.isNotEmpty()) {
                groups = loaded
                activeIndex = 0
                lastRefresh = System.currentTimeMillis()
            }
            loading = false
            delay(60_000)
        }
    }

    LaunchedEffect(groups.size) {
        while (isActive && groups.size > 1) {
            delay(8_000)
            activeIndex = (activeIndex + 1) % groups.size
        }
    }

    val activeGroup = groups.getOrNull(activeIndex.coerceIn(0, (groups.size - 1).coerceAtLeast(0)))
    val fallback = if (loading) {
        "LIVE SCORES • PULLING THE LATEST SPORTS DATA…"
    } else if (lastRefresh > 0L) {
        "LIVE SCORES • FEED UPDATED • ${groups.size} LEAGUES"
    } else {
        "LIVE SCORES • SPORTS FEED TEMPORARILY UNAVAILABLE"
    }
    val line = activeGroup?.let(::tickerLine)?.ifBlank { fallback } ?: fallback

    Box(
        modifier = modifier.fillMaxWidth().height(64.dp).background(Color(0xF2080A10)),
        contentAlignment = Alignment.CenterStart
    ) {
        Row(Modifier.fillMaxSize(), verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier.padding(start = 10.dp, end = 8.dp)
                    .clip(RoundedCornerShape(8.dp))
                    .background(Color(0xFF111722))
                    .padding(horizontal = 11.dp, vertical = 8.dp)
            ) {
                Text("X", color = Color(0xFFFF1744), fontSize = 20.sp, fontWeight = FontWeight.Black)
            }

            Text(
                activeGroup?.league ?: "SPORTS",
                color = Color.White,
                fontSize = 11.sp,
                fontWeight = FontWeight.Black,
                modifier = Modifier.padding(end = 10.dp)
            )

            Box(
                modifier = Modifier
                    .weight(1f)
                    .padding(end = 12.dp)
                    .clip(RoundedCornerShape(8.dp))
                    .background(Color(0xFF0D1118))
                    .padding(horizontal = 10.dp, vertical = 9.dp)
            ) {
                Text(
                    text = line,
                    color = Color(0xFFE5E9F0),
                    fontSize = 12.sp,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    modifier = Modifier.fillMaxWidth().basicMarquee()
                )
            }
        }
    }
}
