package com.xsportsx.app

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.time.Instant
import java.util.Calendar
import java.util.Date
import java.util.Locale
import java.util.TimeZone

private data class LeagueFeed(val sport: String, val id: String, val label: String)
private data class LeagueGame(
    val id: String,
    val away: String,
    val home: String,
    val start: Long,
    val state: String,
    val detail: String,
    val status: String
)

private val leagueFeeds = mapOf(
    "NFL" to LeagueFeed("football", "nfl", "NFL"),
    "NCAA FB" to LeagueFeed("football", "college-football", "NCAA FB"),
    "NBA" to LeagueFeed("basketball", "nba", "NBA"),
    "WNBA" to LeagueFeed("basketball", "wnba", "WNBA"),
    "NCAA BB" to LeagueFeed("basketball", "mens-college-basketball", "NCAA BB"),
    "NCAA WBB" to LeagueFeed("basketball", "womens-college-basketball", "NCAA WBB"),
    "MLB" to LeagueFeed("baseball", "mlb", "MLB"),
    "NCAA Baseball" to LeagueFeed("baseball", "college-baseball", "NCAA Baseball"),
    "NCAA Softball" to LeagueFeed("softball", "college-softball", "NCAA Softball"),
    "NHL" to LeagueFeed("hockey", "nhl", "NHL"),
    "NCAA Hockey" to LeagueFeed("hockey", "mens-college-hockey", "NCAA Hockey"),
    "MLS" to LeagueFeed("soccer", "usa.1", "MLS"),
    "EPL" to LeagueFeed("soccer", "eng.1", "EPL"),
    "UCL" to LeagueFeed("soccer", "uefa.champions", "UCL"),
    "LaLiga" to LeagueFeed("soccer", "esp.1", "LaLiga"),
    "Serie A" to LeagueFeed("soccer", "ita.1", "Serie A"),
    "Bundesliga" to LeagueFeed("soccer", "ger.1", "Bundesliga"),
    "Ligue 1" to LeagueFeed("soccer", "fra.1", "Ligue 1"),
    "NCAA Soccer" to LeagueFeed("soccer", "usa.ncaa", "NCAA Soccer"),
    "NCAA Volleyball" to LeagueFeed("volleyball", "womens-college-volleyball", "NCAA Volleyball"),
    "NCAA Men's Volleyball" to LeagueFeed("volleyball", "mens-college-volleyball", "NCAA Men's Volleyball"),
    "NCAA Lacrosse" to LeagueFeed("lacrosse", "mens-college-lacrosse", "NCAA Lacrosse"),
    "NCAA Wrestling" to LeagueFeed("wrestling", "college-wrestling", "NCAA Wrestling"),
    "NCAA Gymnastics" to LeagueFeed("gymnastics", "womens-college-gymnastics", "NCAA Gymnastics"),
    "PGA" to LeagueFeed("golf", "pga", "PGA"),
    "ATP" to LeagueFeed("tennis", "atp", "ATP"),
    "WTA" to LeagueFeed("tennis", "wta", "WTA"),
    "F1" to LeagueFeed("racing", "f1", "F1"),
    "NASCAR" to LeagueFeed("racing", "nascar", "NASCAR")
)

private fun localDayKey(offset: Int): String {
    val cal = Calendar.getInstance()
    cal.add(Calendar.DAY_OF_YEAR, offset)
    return SimpleDateFormat("yyyyMMdd", Locale.US).format(cal.time)
}

private fun readScoreboard(url: String): JSONObject? = runCatching {
    val c = URL(url).openConnection() as HttpURLConnection
    c.connectTimeout = 5000
    c.readTimeout = 8000
    c.requestMethod = "GET"
    c.setRequestProperty("User-Agent", "XSportsX/1.8")
    c.setRequestProperty("Accept", "application/json")
    try {
        if (c.responseCode in 200..299) {
            c.inputStream.bufferedReader().use { JSONObject(it.readText()) }
        } else null
    } finally {
        c.disconnect()
    }
}.getOrNull()

private suspend fun fetchLeagueGames(feed: LeagueFeed): List<LeagueGame> = withContext(Dispatchers.IO) {
    val all = mutableListOf<LeagueGame>()
    for (offset in 0..2) {
        val date = localDayKey(offset)
        val primary = "https://site.api.espn.com/apis/site/v2/sports/${feed.sport}/${feed.id}/scoreboard?dates=$date&limit=100"
        val json = readScoreboard(primary) ?: run {
            // ESPN occasionally returns a transient failure on the first request.
            kotlinx.coroutines.delay(250)
            readScoreboard(primary)
        } ?: continue

        val events = json.optJSONArray("events") ?: continue
        for (i in 0 until events.length()) {
            val e = events.optJSONObject(i) ?: continue
            val comp = e.optJSONArray("competitions")?.optJSONObject(0) ?: continue
            val teams = comp.optJSONArray("competitors") ?: continue
            var away = "TBD"
            var home = "TBD"
            for (j in 0 until teams.length()) {
                val t = teams.optJSONObject(j) ?: continue
                val name = t.optJSONObject("team")?.optString("displayName").orEmpty().ifBlank { "TBD" }
                if (t.optString("homeAway") == "home") home = name else away = name
            }
            val start = runCatching { Instant.parse(e.optString("date")).toEpochMilli() }.getOrDefault(0L)
            if (start == 0L) continue
            val type = comp.optJSONObject("status")?.optJSONObject("type")
            val state = type?.optString("state").orEmpty().ifBlank { "pre" }
            val detail = type?.optString("shortDetail").orEmpty()
            val status = when (state) {
                "in" -> "LIVE"
                "post" -> "FINAL"
                else -> "UPCOMING"
            }
            all += LeagueGame(e.optString("id"), away, home, start, state, detail, status)
        }
    }
    all.distinctBy { it.id }.sortedBy { it.start }
}

@Composable
fun LeagueScheduleScreen(league: String, onBack: () -> Unit) {
    val feed = leagueFeeds[league]
    var games by remember(league) { mutableStateOf<List<LeagueGame>>(emptyList()) }
    var loading by remember(league) { mutableStateOf(true) }
    var error by remember(league) { mutableStateOf<String?>(null) }
    var mode by remember(league) { mutableStateOf("UPCOMING") }
    var playerFilter by remember { mutableStateOf<String?>(null) }
    var reloadToken by remember(league) { mutableIntStateOf(0) }

    LaunchedEffect(league, reloadToken) {
        if (feed == null) {
            error = "League schedule is not configured"
            loading = false
            return@LaunchedEffect
        }
        loading = true
        error = null
        runCatching { fetchLeagueGames(feed) }
            .onSuccess { games = it }
            .onFailure { error = it.message ?: "Unable to load league schedule" }
        loading = false
    }

    if (playerFilter != null) {
        LiveChannelsScreen(filter = playerFilter, onBack = { playerFilter = null })
        return
    }

    val visible = games.filter { if (mode == "LIVE") it.status == "LIVE" else it.status == "UPCOMING" }
    val grouped = visible.groupBy { dayLabel(it.start) }
    Column(Modifier.fillMaxSize().background(Color(0xFF05060A))) {
        Row(Modifier.fillMaxWidth().padding(20.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("‹", color = Color.White, fontSize = 36.sp, modifier = Modifier.clickable { onBack() })
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(league, color = Color.White, fontSize = 27.sp, fontWeight = FontWeight.Black)
                Text("${league} GAMES • NEXT 3 DAYS", color = Color(0xFF737B89), fontSize = 10.sp, fontWeight = FontWeight.Bold)
            }
            TextButton(onClick = { reloadToken++ }, enabled = !loading) {
                Text(if (loading) "LOADING" else "REFRESH")
            }
        }
        Row(Modifier.padding(horizontal = 20.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(selected = mode == "LIVE", onClick = { mode = "LIVE" }, label = { Text("LIVE") })
            FilterChip(selected = mode == "UPCOMING", onClick = { mode = "UPCOMING" }, label = { Text("UPCOMING") })
        }
        Spacer(Modifier.height(10.dp))
        when {
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = Color(0xFFFF1744))
            }
            error != null -> Box(Modifier.fillMaxSize().padding(28.dp), contentAlignment = Alignment.Center) {
                Text(error!!, color = Color.White)
            }
            visible.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(
                    if (mode == "LIVE") "No live ${league} games right now"
                    else "No upcoming ${league} games in the next 3 days",
                    color = Color(0xFF858B98)
                )
            }
            else -> LazyColumn(contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                grouped.forEach { (day, dayGames) ->
                    item {
                        Text(day, color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Black, modifier = Modifier.padding(top = 8.dp, bottom = 2.dp))
                    }
                    items(dayGames, key = { it.id }) { game ->
                        LeagueGameCard(league, game) { playerFilter = "$league ${game.away} ${game.home}" }
                    }
                }
            }
        }
    }
}

@Composable
private fun LeagueGameCard(league: String, game: LeagueGame, onWatch: () -> Unit) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Color(0xFF10141C)).padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(game.away, color = Color.White, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text("@ ${game.home}", color = Color(0xFFB6BDCA), fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Spacer(Modifier.height(5.dp))
            Text(if (game.status == "LIVE") "LIVE • ${game.detail}" else formatGameTime(game.start), color = if (game.status == "LIVE") Color(0xFFFF536C) else Color(0xFF7F8795), fontSize = 10.sp)
        }
        if (game.status == "LIVE") {
            Button(onClick = onWatch, colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFF1744))) { Text("WATCH") }
        } else {
            Text("UPCOMING", color = Color(0xFF9BA4B2), fontSize = 9.sp, fontWeight = FontWeight.Black)
        }
    }
}

private fun dayLabel(epoch: Long): String = SimpleDateFormat("EEE, MMM d", Locale.US).apply { timeZone = TimeZone.getDefault() }.format(Date(epoch))
private fun formatGameTime(epoch: Long): String = SimpleDateFormat("EEE • h:mm a", Locale.US).apply { timeZone = TimeZone.getDefault() }.format(Date(epoch))
