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
import kotlinx.coroutines.withTimeoutOrNull
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

private fun dateString(offset: Int): String {
    val format = SimpleDateFormat("yyyyMMdd", Locale.US).apply {
        timeZone = TimeZone.getTimeZone("UTC")
    }
    val calendar = Calendar.getInstance(TimeZone.getTimeZone("UTC"))
    calendar.add(Calendar.DAY_OF_YEAR, offset)
    return format.format(calendar.time)
}

private fun httpBody(url: String, accept: String = "application/json"): String? {
    repeat(2) { attempt ->
        val connection = try { URL(url).openConnection() as HttpURLConnection } catch (_: Exception) { return@repeat }
        try {
            connection.connectTimeout = 4000
            connection.readTimeout = 6500
            connection.requestMethod = "GET"
            connection.instanceFollowRedirects = true
            connection.setRequestProperty("User-Agent", "XSportsX/1.8")
            connection.setRequestProperty("Accept", accept)
            val code = connection.responseCode
            if (code in 200..299) {
                return connection.inputStream.bufferedReader().use { it.readText() }
            }
            if (code !in 408..429 && code !in 500..599) return null
        } catch (_: Exception) {
            if (attempt == 1) return null
        } finally {
            connection.disconnect()
        }
        if (attempt == 0) Thread.sleep(250)
    }
    return null
}

private fun getJson(url: String): JSONObject? = httpBody(url)?.let { body ->
    runCatching { JSONObject(body) }.getOrNull()
}

private fun eventTime(event: JSONObject): Long = runCatching {
    java.time.Instant.parse(event.optString("date")).toEpochMilli()
}.getOrDefault(0L)

private fun tickerPriority(kind: String): Int = when (kind) {
    "LIVE" -> 0
    "UPCOMING" -> 1
    "FINAL" -> 2
    "NEWS" -> 3
    else -> 4
}

private suspend fun loadLeague(league: TickerLeague): TickerLeagueGroup? = withContext(Dispatchers.IO) {
    val url = "https://site.api.espn.com/apis/site/v2/sports/${league.sport}/${league.id}/scoreboard?dates=${dateString(0)}&limit=50"
    val json = getJson(url) ?: return@withContext null
    val events = json.optJSONArray("events") ?: return@withContext TickerLeagueGroup(league.name, emptyList())
    val now = System.currentTimeMillis()
    val items = buildList {
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
                if (team.optString("homeAway") == "home") {
                    home = name
                    homeScore = team.optString("score")
                } else {
                    away = name
                    awayScore = team.optString("score")
                }
            }
            val statusType = competition.optJSONObject("status")?.optJSONObject("type")
            val state = statusType?.optString("state").orEmpty().ifBlank { "pre" }
            val detail = statusType?.optString("shortDetail").orEmpty()
            val timestamp = eventTime(event)
            val kind = when (state) {
                "in" -> "LIVE"
                "post" -> "FINAL"
                else -> "UPCOMING"
            }
            val text = if (kind == "UPCOMING") {
                "$away @ $home${detail.takeIf { it.isNotBlank() }?.let { " • $it" } ?: ""}"
            } else {
                "$away $awayScore  •  $home $homeScore"
            }
            if (timestamp == 0L || timestamp >= now - 36L * 60L * 60L * 1000L) {
                add(TickerItem(kind, league.name, text, timestamp))
            }
        }
    }
    TickerLeagueGroup(
        league.name,
        items.sortedWith(compareBy<TickerItem> { tickerPriority(it.kind) }.thenBy { it.timestamp }).take(12)
    )
}

private suspend fun loadEspnNews(): TickerLeagueGroup? = withContext(Dispatchers.IO) {
    val urls = listOf(
        "https://site.api.espn.com/apis/site/v2/sports/news?region=us&lang=en&limit=12",
        "https://site.api.espn.com/apis/site/v2/sports/general/news?region=us&lang=en&limit=12"
    )
    for (url in urls) {
        val articles = getJson(url)?.optJSONArray("articles") ?: continue
        val items = buildList {
            for (i in 0 until articles.length()) {
                val article = articles.optJSONObject(i) ?: continue
                val headline = article.optString("headline").trim()
                if (headline.isBlank()) continue
                val timestamp = runCatching {
                    java.time.Instant.parse(article.optString("published")).toEpochMilli()
                }.getOrDefault(0L)
                add(TickerItem("NEWS", "BREAKING", headline, timestamp))
            }
        }.sortedByDescending { it.timestamp }.take(8)
        if (items.isNotEmpty()) return@withContext TickerLeagueGroup("BREAKING NEWS", items)
    }
    null
}

private suspend fun loadPrimaryGroups(): List<TickerLeagueGroup> = coroutineScope {
    val groups = mutableListOf<TickerLeagueGroup>()
    tickerLeagues.chunked(4).forEach { batch ->
        val results = batch.map { league -> async { loadLeague(league) } }.awaitAll()
        groups += results.filterNotNull().filter { it.items.isNotEmpty() }
    }
    groups
}

private suspend fun loadFallbackScores(): List<TickerLeagueGroup> {
    val group = loadLeague(TickerLeague("NFL", "football", "nfl"))
    return if (group?.items?.isNotEmpty() == true) listOf(group) else emptyList()
}

private suspend fun loadTickerGroups(): List<TickerLeagueGroup> = withTimeoutOrNull(30_000L) {
    val primary = runCatching { loadPrimaryGroups() }.getOrDefault(emptyList())
    val news = runCatching { loadEspnNews() }.getOrNull()
    if (primary.isNotEmpty()) {
        return@withTimeoutOrNull primary + listOfNotNull(news)
    }
    val fallback = runCatching { loadFallbackScores() }.getOrDefault(emptyList())
    fallback + listOfNotNull(news)
} ?: emptyList()

private fun tickerLine(group: TickerLeagueGroup): String = group.items.joinToString("     •     ") { item ->
    "${item.kind}  ${item.text}"
}

@Composable
fun HomeSportsTicker(modifier: Modifier = Modifier) {
    var groups by remember { mutableStateOf<List<TickerLeagueGroup>>(emptyList()) }
    var activeIndex by remember { mutableIntStateOf(0) }
    var loading by remember { mutableStateOf(true) }
    var lastGoodRefresh by remember { mutableLongStateOf(0L) }
    var feedFailed by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        while (isActive) {
            loading = true
            val loaded = runCatching { loadTickerGroups() }.getOrDefault(emptyList())
            if (loaded.isNotEmpty()) {
                groups = loaded
                activeIndex = 0
                lastGoodRefresh = System.currentTimeMillis()
                feedFailed = false
            } else {
                feedFailed = groups.isEmpty()
            }
            loading = false
            delay(60_000L)
        }
    }

    LaunchedEffect(groups.size) {
        while (isActive && groups.size > 1) {
            delay(7_000L)
            activeIndex = (activeIndex + 1) % groups.size
        }
    }

    val activeGroup = groups.getOrNull(activeIndex.coerceIn(0, (groups.size - 1).coerceAtLeast(0)))
    val fallbackText = when {
        loading && groups.isEmpty() -> "LIVE SCORES • CONNECTING TO SPORTS FEEDS…"
        feedFailed && lastGoodRefresh == 0L -> "LIVE SCORES • SPORTS FEED TEMPORARILY UNAVAILABLE"
        groups.isEmpty() -> "LIVE SCORES • NO LIVE SPORTS DATA RIGHT NOW"
        else -> "LIVE SCORES • FEED UPDATED"
    }
    val line = activeGroup?.let(::tickerLine)?.ifBlank { fallbackText } ?: fallbackText

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
