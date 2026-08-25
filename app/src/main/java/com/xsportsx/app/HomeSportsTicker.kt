package com.xsportsx.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
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

data class TickerItem(val kind: String, val league: String, val text: String)

data class TickerLeague(val name: String, val sport: String, val id: String)

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
    val start = fmt.format(cal.time)
    cal.add(Calendar.DAY_OF_YEAR, 1)
    return "$start-${fmt.format(cal.time)}"
}

private fun getJson(url: String): JSONObject? = try {
    val c = URL(url).openConnection() as HttpURLConnection
    c.connectTimeout = 4500
    c.readTimeout = 4500
    c.requestMethod = "GET"
    c.setRequestProperty("User-Agent", "XSportsX/1.4")
    c.setRequestProperty("Accept", "application/json")
    if (c.responseCode !in 200..299) return null
    c.inputStream.bufferedReader().use { JSONObject(it.readText()) }
} catch (_: Exception) { null }

private suspend fun loadScores(): List<TickerItem> = coroutineScope {
    val range = dateRange()
    tickerLeagues.map { league ->
        async(Dispatchers.IO) {
            val url = "https://site.api.espn.com/apis/site/v2/sports/${league.sport}/${league.id}/scoreboard?dates=$range&limit=50"
            val json = getJson(url) ?: return@async emptyList()
            val events = json.optJSONArray("events") ?: return@async emptyList()
            buildList {
                for (i in 0 until events.length()) {
                    val e = events.optJSONObject(i) ?: continue
                    val c = e.optJSONArray("competitions")?.optJSONObject(0) ?: continue
                    val competitors = c.optJSONArray("competitors") ?: continue
                    var home = "TBD"
                    var away = "TBD"
                    var homeScore = ""
                    var awayScore = ""
                    for (j in 0 until competitors.length()) {
                        val team = competitors.optJSONObject(j) ?: continue
                        val name = team.optJSONObject("team")?.optString("abbreviation")?.ifBlank { team.optJSONObject("team")?.optString("shortDisplayName") } ?: "TBD"
                        val score = team.optString("score")
                        if (team.optString("homeAway") == "home") { home = name; homeScore = score } else { away = name; awayScore = score }
                    }
                    val state = c.optJSONObject("status")?.optJSONObject("type")?.optString("state") ?: "pre"
                    val detail = c.optJSONObject("status")?.optJSONObject("type")?.optString("shortDetail") ?: ""
                    val kind = when (state) { "in" -> "LIVE"; "post" -> "FINAL"; else -> "UPCOMING" }
                    val scoreText = if (kind == "UPCOMING") "$away @ $home • $detail" else "$away $awayScore • $home $homeScore"
                    add(TickerItem(kind, league.name, scoreText))
                }
            }
        }
    }.awaitAll().flatten()
}

private suspend fun loadNews(): List<TickerItem> = coroutineScope {
    listOf("football", "basketball", "baseball", "hockey", "soccer", "mma").map { sport ->
        async(Dispatchers.IO) {
            val json = getJson("https://now.core.api.espn.com/v1/sports/news?limit=12&sport=$sport") ?: return@async emptyList()
            val headlines = json.optJSONArray("headlines") ?: return@async emptyList()
            buildList {
                for (i in 0 until headlines.length()) {
                    val h = headlines.optJSONObject(i) ?: continue
                    val title = h.optString("headline").trim()
                    if (title.isNotEmpty()) add(TickerItem("NEWS", sport.uppercase(Locale.US), title))
                }
            }
        }
    }.awaitAll().flatten()
}

private suspend fun fetchTicker(): List<TickerItem> = withContext(Dispatchers.IO) {
    val scores = loadScores()
    val news = loadNews()
    val live = scores.filter { it.kind == "LIVE" }
    val finals = scores.filter { it.kind == "FINAL" }.take(8)
    val upcoming = scores.filter { it.kind == "UPCOMING" }.take(10)
    val headlines = news.take(10)
    (live + finals + headlines + upcoming).ifEmpty {
        listOf(TickerItem("NEWS", "XSPORTSX", "Checking ESPN scores, finals, schedules and breaking sports news…"))
    }
}

@Composable
fun HomeSportsTicker(modifier: Modifier = Modifier) {
    var items by remember { mutableStateOf<List<TickerItem>>(emptyList()) }
    LaunchedEffect(Unit) {
        while (isActive) {
            items = fetchTicker()
            delay(60_000)
        }
    }
    Box(
        modifier.fillMaxWidth().height(58.dp).background(Color(0xF2080A10)),
        contentAlignment = Alignment.CenterStart
    ) {
        Row(Modifier.fillMaxSize(), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.padding(start = 12.dp, end = 8.dp).clip(RoundedCornerShape(8.dp)).background(Color(0xFFFF1744)).padding(horizontal = 10.dp, vertical = 7.dp)) {
                Text("X LIVE", color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black)
            }
            LazyRow(
                modifier = Modifier.weight(1f),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                contentPadding = PaddingValues(end = 14.dp)
            ) {
                items(items) { item ->
                    val accent = when (item.kind) { "LIVE" -> Color(0xFFFF1744); "FINAL" -> Color(0xFFB7C1D1); "NEWS" -> Color(0xFFFF6D00); else -> Color(0xFF74809A) }
                    Row(Modifier.clip(RoundedCornerShape(9.dp)).background(Color(0xFF111722)).padding(horizontal = 10.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text(item.kind, color = accent, fontSize = 8.sp, fontWeight = FontWeight.Black)
                        Spacer(Modifier.width(7.dp))
                        Text(item.league, color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Black)
                        Spacer(Modifier.width(7.dp))
                        Text(item.text, color = Color(0xFFC3CBD8), fontSize = 9.sp, maxLines = 1)
                    }
                }
            }
        }
    }
}
