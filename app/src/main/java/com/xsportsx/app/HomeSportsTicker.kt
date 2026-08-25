package com.xsportsx.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
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

data class TickerItem(val kind: String, val league: String, val text: String)
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
    val start = fmt.format(cal.time)
    cal.add(Calendar.DAY_OF_YEAR, 1)
    return "$start-${fmt.format(cal.time)}"
}

private fun getJson(url: String): JSONObject? = try {
    val c = URL(url).openConnection() as HttpURLConnection
    c.connectTimeout = 3000
    c.readTimeout = 3000
    c.requestMethod = "GET"
    c.setRequestProperty("User-Agent", "XSportsX/1.5")
    c.setRequestProperty("Accept", "application/json")
    if (c.responseCode !in 200..299) return null
    c.inputStream.bufferedReader().use { JSONObject(it.readText()) }
} catch (_: Exception) { null }

private suspend fun loadLeague(league: TickerLeague): TickerLeagueGroup = withContext(Dispatchers.IO) {
    val url = "https://site.api.espn.com/apis/site/v2/sports/${league.sport}/${league.id}/scoreboard?dates=${dateRange()}&limit=50"
    val json = getJson(url)
    val events = json?.optJSONArray("events")
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
                    val name = teamObj?.optString("abbreviation")?.ifBlank {
                        teamObj.optString("shortDisplayName")
                    }.orEmpty().ifBlank { "TBD" }
                    val score = team.optString("score")
                    if (team.optString("homeAway") == "home") {
                        home = name
                        homeScore = score
                    } else {
                        away = name
                        awayScore = score
                    }
                }
                val status = competition.optJSONObject("status")?.optJSONObject("type")
                val state = status?.optString("state") ?: "pre"
                val detail = status?.optString("shortDetail") ?: ""
                val kind = when (state) {
                    "in" -> "LIVE"
                    "post" -> "FINAL"
                    else -> "UPCOMING"
                }
                val text = if (kind == "UPCOMING") {
                    "$away @ $home • $detail"
                } else {
                    "$away $awayScore  •  $home $homeScore"
                }
                add(TickerItem(kind, league.name, text))
            }
        }
    }
    TickerLeagueGroup(league.name, items.take(12))
}

private suspend fun loadTickerGroups(): List<TickerLeagueGroup> = coroutineScope {
    tickerLeagues.map { league ->
        async { loadLeague(league) }
    }.awaitAll().filter { it.items.isNotEmpty() }
}

@Composable
fun HomeSportsTicker(modifier: Modifier = Modifier) {
    var groups by remember { mutableStateOf<List<TickerLeagueGroup>>(emptyList()) }
    var activeIndex by remember { mutableIntStateOf(0) }

    LaunchedEffect(Unit) {
        while (isActive) {
            groups = loadTickerGroups()
            activeIndex = 0
            delay(60_000)
        }
    }

    LaunchedEffect(groups) {
        while (isActive && groups.isNotEmpty()) {
            delay(6_000)
            if (groups.isNotEmpty()) {
                activeIndex = (activeIndex + 1) % groups.size
            }
        }
    }

    val activeGroup = groups.getOrNull(activeIndex)
    val visibleItems = activeGroup?.items ?: listOf(
        TickerItem("NEWS", "XSPORTSX", "Live scores and schedules loading…")
    )

    Box(
        modifier = modifier.fillMaxWidth().height(58.dp).background(Color(0xF2080A10)),
        contentAlignment = Alignment.CenterStart
    ) {
        Row(Modifier.fillMaxSize(), verticalAlignment = Alignment.CenterVertically) {
            // XSportsX replaces the ESPN logo. No advertising is included.
            Box(
                Modifier
                    .padding(start = 10.dp, end = 8.dp)
                    .clip(RoundedCornerShape(7.dp))
                    .background(Color(0xFF111722))
                    .padding(horizontal = 9.dp, vertical = 6.dp)
            ) {
                Text("X", color = Color(0xFFFF1744), fontSize = 16.sp, fontWeight = FontWeight.Black)
            }

            Text(
                text = activeGroup?.league ?: "SPORTS",
                color = Color.White,
                fontSize = 10.sp,
                fontWeight = FontWeight.Black,
                modifier = Modifier.padding(end = 8.dp)
            )

            LazyRow(
                modifier = Modifier.weight(1f),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                contentPadding = PaddingValues(end = 14.dp)
            ) {
                items(visibleItems) { item ->
                    val accent = when (item.kind) {
                        "LIVE" -> Color(0xFFFF1744)
                        "FINAL" -> Color(0xFFB7C1D1)
                        else -> Color(0xFF74809A)
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(item.kind, color = accent, fontSize = 8.sp, fontWeight = FontWeight.Black)
                        Spacer(Modifier.width(6.dp))
                        Text(item.text, color = Color(0xFFD7DDE7), fontSize = 10.sp, maxLines = 1)
                    }
                }
            }
        }
    }
}
