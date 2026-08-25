package com.xsportsx.app

import androidx.compose.foundation.background
import androidx.compose.foundation.basicMarquee
import androidx.compose.foundation.layout.*
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.supervisorScope
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale
import java.util.TimeZone

data class TickerItem(val kind: String, val league: String, val text: String, val timestamp: Long = 0L)
data class TickerLeague(val name: String, val sport: String, val id: String)
data class TickerLeagueGroup(val league: String, val items: List<TickerItem>)

private val tickerLeagues = listOf(
    TickerLeague("NFL", "football", "nfl"), TickerLeague("NCAA FB", "football", "college-football"),
    TickerLeague("NBA", "basketball", "nba"), TickerLeague("WNBA", "basketball", "wnba"),
    TickerLeague("NCAA BB", "basketball", "mens-college-basketball"), TickerLeague("MLB", "baseball", "mlb"),
    TickerLeague("NHL", "hockey", "nhl"), TickerLeague("MLS", "soccer", "usa.1"),
    TickerLeague("EPL", "soccer", "eng.1"), TickerLeague("UCL", "soccer", "uefa.champions"),
    TickerLeague("LaLiga", "soccer", "esp.1"), TickerLeague("Serie A", "soccer", "ita.1"),
    TickerLeague("Bundesliga", "soccer", "ger.1"), TickerLeague("Ligue 1", "soccer", "fra.1"),
    TickerLeague("UFC", "mma", "ufc"), TickerLeague("BOXING", "boxing", "boxing")
)

private val newsLeagues = tickerLeagues.filter { it.id != "boxing" }

private fun todayUtc(): String = SimpleDateFormat("yyyyMMdd", Locale.US).apply {
    timeZone = TimeZone.getTimeZone("UTC")
}.format(Calendar.getInstance(TimeZone.getTimeZone("UTC")).time)

private suspend fun getJson(url: String): JSONObject? = withContext(Dispatchers.IO) {
    withTimeoutOrNull(5500L) {
        val connection = runCatching { URL(url).openConnection() as HttpURLConnection }.getOrNull() ?: return@withTimeoutOrNull null
        try {
            connection.connectTimeout = 2500
            connection.readTimeout = 4500
            connection.requestMethod = "GET"
            connection.instanceFollowRedirects = true
            connection.setRequestProperty("User-Agent", "XSportsX/1.9 Android")
            connection.setRequestProperty("Accept", "application/json")
            if (connection.responseCode !in 200..299) null else runCatching {
                JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
            }.getOrNull()
        } catch (_: Exception) { null } finally { connection.disconnect() }
    }
}

private fun eventTime(event: JSONObject): Long = runCatching { Instant.parse(event.optString("date")).toEpochMilli() }.getOrDefault(0L)

private suspend fun loadLeague(league: TickerLeague): TickerLeagueGroup? {
    val root = getJson("https://site.api.espn.com/apis/site/v2/sports/${league.sport}/${league.id}/scoreboard?dates=${todayUtc()}&limit=100") ?: return null
    val events = root.optJSONArray("events") ?: return TickerLeagueGroup(league.name, emptyList())
    val now = System.currentTimeMillis()
    val items = buildList {
        for (i in 0 until events.length()) {
            val event = events.optJSONObject(i) ?: continue
            val competition = event.optJSONArray("competitions")?.optJSONObject(0) ?: continue
            val teams = competition.optJSONArray("competitors") ?: continue
            var home = "TBD"; var away = "TBD"; var homeScore = ""; var awayScore = ""
            for (j in 0 until teams.length()) {
                val competitor = teams.optJSONObject(j) ?: continue
                val team = competitor.optJSONObject("team")
                val name = team?.optString("abbreviation")?.ifBlank { team.optString("shortDisplayName") }.orEmpty().ifBlank { competitor.optString("displayName").ifBlank { "TBD" } }
                if (competitor.optString("homeAway") == "home") { home = name; homeScore = competitor.optString("score") } else { away = name; awayScore = competitor.optString("score") }
            }
            val type = competition.optJSONObject("status")?.optJSONObject("type")
            val state = type?.optString("state").orEmpty()
            val detail = type?.optString("shortDetail").orEmpty()
            val timestamp = eventTime(event)
            val kind = when (state) { "in" -> "LIVE"; "post" -> "FINAL"; else -> "UPCOMING" }
            if (timestamp == 0L || timestamp >= now - 36L * 60L * 60L * 1000L) {
                val text = if (kind == "UPCOMING") "$away @ $home${detail.takeIf { it.isNotBlank() }?.let { " • $it" } ?: ""}" else "$away $awayScore • $home $homeScore${detail.takeIf { it.isNotBlank() }?.let { " • $it" } ?: ""}"
                add(TickerItem(kind, league.name, text, timestamp))
            }
        }
    }
    return TickerLeagueGroup(league.name, items.sortedWith(compareBy<TickerItem> { when (it.kind) { "LIVE" -> 0; "UPCOMING" -> 1; else -> 2 } }.thenBy { it.timestamp }).take(12))
}

private suspend fun loadNews(league: TickerLeague): TickerLeagueGroup? {
    val root = getJson("https://site.api.espn.com/apis/site/v2/sports/${league.sport}/${league.id}/news?limit=6") ?: return null
    val articles = root.optJSONArray("articles") ?: return null
    val items = buildList {
        for (i in 0 until articles.length()) {
            val article = articles.optJSONObject(i) ?: continue
            val headline = article.optString("headline").trim()
            if (headline.isNotBlank()) add(TickerItem("NEWS", league.name, headline, eventTime(article)))
        }
    }
    return TickerLeagueGroup("NEWS • ${league.name}", items.take(6))
}

private suspend fun loadTickerGroups(): List<TickerLeagueGroup> = supervisorScope {
    val scoreResults = tickerLeagues.map { league -> async { runCatching { loadLeague(league) }.getOrNull() } }.awaitAll()
    val newsResults = newsLeagues.map { league -> async { runCatching { loadNews(league) }.getOrNull() } }.awaitAll()
    val games = scoreResults.filterNotNull().filter { it.items.isNotEmpty() }
    val news = newsResults.filterNotNull().filter { it.items.isNotEmpty() }
    games.sortedWith(compareBy<TickerLeagueGroup> { if (it.items.any { x -> x.kind == "LIVE" }) 0 else 1 }.thenBy { it.league }) + news
}

private fun line(group: TickerLeagueGroup): String = group.items.joinToString("     •     ") { "${it.kind}  [${it.league}]  ${it.text}" }

@Composable
fun HomeSportsTicker(modifier: Modifier = Modifier) {
    var groups by remember { mutableStateOf<List<TickerLeagueGroup>>(emptyList()) }
    var index by remember { mutableIntStateOf(0) }
    var loading by remember { mutableStateOf(true) }
    var failed by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) {
        while (isActive) {
            loading = true
            val loaded = runCatching { loadTickerGroups() }.getOrDefault(emptyList())
            if (loaded.isNotEmpty()) {
                groups = loaded
                index = index.coerceIn(0, loaded.lastIndex)
                failed = false
            } else if (groups.isEmpty()) {
                failed = true
            }
            loading = false
            delay(60_000L)
        }
    }
    val group = groups.getOrNull(index.coerceIn(0, (groups.size - 1).coerceAtLeast(0)))
    val text = group?.let(::line)?.takeIf { it.isNotBlank() } ?: when {
        loading -> "SPORTS FEED  •  LOADING"
        failed -> "SPORTS FEED  •  TEMPORARILY UNAVAILABLE"
        else -> "SPORTS FEED  •  NO GAMES / NEWS AVAILABLE"
    }
    Row(
        modifier.fillMaxWidth().height(42.dp).background(Color(0xEE07090E)).padding(horizontal = 18.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text("X", color = Color(0xFFFF1744), fontWeight = FontWeight.Black, fontSize = 20.sp)
        Spacer(Modifier.width(10.dp))
        TickerMarquee(text, Modifier.weight(1f)) {
            if (groups.size > 1) index = (index + 1) % groups.size
        }
    }
}

@Composable
private fun TickerMarquee(text: String, modifier: Modifier, onFinished: () -> Unit) {
    val density = LocalDensity.current
    var viewportWidthPx by remember { mutableIntStateOf(0) }
    var textWidthPx by remember(text) { mutableIntStateOf(0) }
    LaunchedEffect(text, viewportWidthPx, textWidthPx) {
        if (viewportWidthPx <= 0 || textWidthPx <= 0) return@LaunchedEffect
        val velocityPxPerSecond = with(density) { 55.dp.toPx() }
        val duration = if (textWidthPx <= viewportWidthPx) 4_500L else ((textWidthPx + viewportWidthPx) / velocityPxPerSecond * 1_000L + 900L).toLong().coerceAtLeast(5_000L)
        delay(duration)
        onFinished()
    }
    BoxWithConstraints(modifier.fillMaxHeight().onSizeChanged { viewportWidthPx = it.width }) {
        Text(
            text,
            modifier = Modifier.fillMaxWidth().basicMarquee(iterations = 1, repeatDelayMillis = 0, initialDelayMillis = 650, velocity = 55.dp),
            onTextLayout = { textWidthPx = it.size.width },
            color = Color.White,
            fontWeight = FontWeight.Bold,
            fontSize = 12.sp,
            maxLines = 1
        )
    }
}
