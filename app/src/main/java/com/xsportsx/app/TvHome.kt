package com.xsportsx.app

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
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

private val TvRed = Color(0xFFFF1838)
private val TvBlue = Color(0xFF2E8BFF)
private val TvBg = Color(0xFF03060B)
private val TvPanel = Color(0xFF0B111A)
private val TvPanel2 = Color(0xFF111923)
private val TvMuted = Color(0xFF8993A2)

private data class TvGame(
    val league: String,
    val home: String,
    val away: String,
    val score: String,
    val status: String,
    val network: String,
    val live: Boolean,
    val timestamp: Long
)
private data class TvSport(val name: String, val glyph: String)
private data class TvNetwork(val name: String, val mark: String)

private data class TvLeague(val name: String, val sport: String, val id: String)
private val liveLeagues = listOf(
    TvLeague("NFL", "football", "nfl"),
    TvLeague("NCAA FB", "football", "college-football"),
    TvLeague("NBA", "basketball", "nba"),
    TvLeague("WNBA", "basketball", "wnba"),
    TvLeague("NCAA BB", "basketball", "mens-college-basketball"),
    TvLeague("MLB", "baseball", "mlb"),
    TvLeague("NHL", "hockey", "nhl"),
    TvLeague("MLS", "soccer", "usa.1"),
    TvLeague("EPL", "soccer", "eng.1")
)

private val tvSports = listOf(
    TvSport("NFL", "FB"), TvSport("NBA", "BB"), TvSport("NCAA FB", "NCAA"), TvSport("NCAA BB", "NCAA"),
    TvSport("MLB", "BASE"), TvSport("NHL", "ICE"), TvSport("UFC", "OCT"), TvSport("BOXING", "BOX")
)

private val tvNetworks = listOf(
    TvNetwork("ESPN", "ESPN"), TvNetwork("ESPN2", "ESPN2"), TvNetwork("ESPNU", "ESPNU"),
    TvNetwork("NFL NETWORK", "NFL"), TvNetwork("FS1", "FS1"), TvNetwork("CBS SPORTS", "CBS"),
    TvNetwork("SEC NETWORK", "SEC"), TvNetwork("ACC NETWORK", "ACC"), TvNetwork("BIG TEN NETWORK", "B1G"),
    TvNetwork("ESPN+", "ESPN+")
)

private fun dateRange(): String {
    val fmt = SimpleDateFormat("yyyyMMdd", Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") }
    val cal = Calendar.getInstance(TimeZone.getTimeZone("UTC"))
    cal.add(Calendar.DAY_OF_YEAR, -1)
    val yesterday = fmt.format(cal.time)
    cal.add(Calendar.DAY_OF_YEAR, 2)
    return "$yesterday-${fmt.format(cal.time)}"
}

private fun tvJson(url: String): JSONObject? {
    val c = try { URL(url).openConnection() as HttpURLConnection } catch (_: Exception) { return null }
    return try {
        c.connectTimeout = 3000
        c.readTimeout = 5000
        c.requestMethod = "GET"
        c.setRequestProperty("User-Agent", "XSportsX/1.6")
        c.setRequestProperty("Accept", "application/json")
        if (c.responseCode !in 200..299) null else c.inputStream.bufferedReader().use { JSONObject(it.readText()) }
    } catch (_: Exception) { null } finally { c.disconnect() }
}

private fun eventMillis(event: JSONObject): Long = try {
    java.time.Instant.parse(event.optString("date")).toEpochMilli()
} catch (_: Exception) { 0L }

private suspend fun loadTvGames(): List<TvGame> = withContext(Dispatchers.IO) {
    val now = System.currentTimeMillis()
    liveLeagues.flatMap { league ->
        val url = "https://site.api.espn.com/apis/site/v2/sports/${league.sport}/${league.id}/scoreboard?dates=${dateRange()}&limit=50"
        val events = tvJson(url)?.optJSONArray("events") ?: return@flatMap emptyList()
        buildList {
            for (i in 0 until events.length()) {
                val event = events.optJSONObject(i) ?: continue
                val competition = event.optJSONArray("competitions")?.optJSONObject(0) ?: continue
                val status = competition.optJSONObject("status")?.optJSONObject("type") ?: continue
                val state = status.optString("state")
                val isLive = state == "in"
                if (!isLive) continue
                val competitors = competition.optJSONArray("competitors") ?: continue
                var home = "TBD"; var away = "TBD"; var homeScore = "0"; var awayScore = "0"
                for (j in 0 until competitors.length()) {
                    val team = competitors.optJSONObject(j) ?: continue
                    val name = team.optJSONObject("team")?.optString("abbreviation").orEmpty().ifBlank { "TBD" }
                    val score = team.optString("score").ifBlank { "0" }
                    if (team.optString("homeAway") == "home") { home = name; homeScore = score }
                    else { away = name; awayScore = score }
                }
                val detail = status.optString("shortDetail").ifBlank { status.optString("detail") }.ifBlank { "LIVE" }
                val network = competition.optJSONArray("broadcasts")?.optJSONObject(0)?.optJSONArray("names")?.optString(0).orEmpty().ifBlank { "LIVE" }
                add(TvGame(league.name, home, away, "$awayScore  •  $homeScore", detail, network, true, eventMillis(event)))
            }
        }
    }.sortedByDescending { it.timestamp }.take(20)
}

@Composable
fun TvHome(onConnect: () -> Unit = {}, onNetwork: (String) -> Unit = {}) {
    var selectedNav by remember { mutableStateOf("HOME") }
    var liveGames by remember { mutableStateOf<List<TvGame>>(emptyList()) }
    var loadingLive by remember { mutableStateOf(true) }
    val scroll = rememberScrollState()

    LaunchedEffect(Unit) {
        while (isActive) {
            loadingLive = liveGames.isEmpty()
            val result = runCatching { loadTvGames() }.getOrDefault(emptyList())
            if (result.isNotEmpty()) liveGames = result
            loadingLive = false
            delay(60_000)
        }
    }

    Box(Modifier.fillMaxSize().background(TvBg)) {
        Row(Modifier.fillMaxSize()) {
            TvNav(selectedNav) { selectedNav = it }
            Column(Modifier.weight(1f).fillMaxHeight().verticalScroll(scroll).padding(start = 22.dp, end = 30.dp, top = 20.dp, bottom = 76.dp)) {
                TvTopBar(onConnect)
                Spacer(Modifier.height(14.dp))
                when (selectedNav) {
                    "HOME" -> {
                        TvHero(onConnect)
                        Spacer(Modifier.height(18.dp))
                        TvSection("LIVE NOW", if (liveGames.isEmpty()) "Waiting for live scores" else "${liveGames.size} LIVE")
                        if (liveGames.isNotEmpty()) TvGameRow(liveGames, onNetwork) else TvLiveEmpty(loadingLive)
                        Spacer(Modifier.height(16.dp))
                        TvSection("TOP SPORTS")
                        TvSportRow(tvSports) { sport -> onNetwork(sport.name) }
                        Spacer(Modifier.height(16.dp))
                        TvNetworksBlock(onNetwork)
                    }
                    "LIVE NOW" -> {
                        TvSection("LIVE NOW", if (liveGames.isEmpty()) "No games live right now" else "${liveGames.size} LIVE")
                        if (liveGames.isNotEmpty()) TvGameRow(liveGames, onNetwork) else TvLiveEmpty(loadingLive)
                    }
                    "UPCOMING" -> {
                        TvSection("UPCOMING")
                        TvEmpty("Upcoming events will appear here")
                    }
                    "NETWORKS" -> {
                        TvSection("SPORTS NETWORKS")
                        TvNetworkGrid(tvNetworks, onNetwork)
                    }
                    "FAVORITES" -> {
                        TvSection("FAVORITES")
                        TvEmpty("Your favorite leagues and networks will appear here")
                    }
                    "SETTINGS" -> TvSettings(onConnect)
                }
            }
        }
        HomeSportsTicker(Modifier.align(Alignment.BottomCenter).fillMaxWidth())
    }
}

@Composable
private fun TvLiveEmpty(loading: Boolean) {
    Box(Modifier.fillMaxWidth().height(170.dp).clip(RoundedCornerShape(16.dp)).background(TvPanel).border(1.dp, TvRed.copy(alpha = .18f), RoundedCornerShape(16.dp)), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(if (loading) "LOADING LIVE GAMES…" else "NO LIVE GAMES RIGHT NOW", color = Color.White, fontSize = 15.sp, fontWeight = FontWeight.Black)
            Text("Live scores refresh automatically", color = TvMuted, fontSize = 10.sp)
        }
    }
}

@Composable
private fun TvNav(selected: String, onSelect: (String) -> Unit) {
    Column(Modifier.width(210.dp).fillMaxHeight().background(Brush.horizontalGradient(listOf(Color(0xFF071019), Color(0xFF04070C)))).padding(start = 22.dp, top = 22.dp, end = 18.dp, bottom = 72.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) { Text("X", color = TvRed, fontSize = 46.sp, fontWeight = FontWeight.Black); Text("SPORTS", color = Color.White, fontSize = 25.sp, fontWeight = FontWeight.Black); Text("X", color = TvRed, fontSize = 25.sp, fontWeight = FontWeight.Black) }
        Spacer(Modifier.height(30.dp))
        listOf("⌂" to "HOME", "●" to "LIVE NOW", "▣" to "UPCOMING", "▤" to "NETWORKS", "★" to "FAVORITES", "⚙" to "SETTINGS").forEach { (icon, label) -> TvNavItem(icon, label, selected == label) { onSelect(label) } }
        Spacer(Modifier.height(22.dp)); Text("SPORTS", color = TvMuted, fontSize = 9.sp, fontWeight = FontWeight.Black, letterSpacing = 1.4.sp); Spacer(Modifier.height(6.dp))
        tvSports.forEach { sport -> TvSportNavItem(sport) { onSelect(sport.name) } }
        Spacer(Modifier.weight(1f)); Text("XSportsX TV", color = Color(0xFF596371), fontSize = 10.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun TvNavItem(icon: String, label: String, active: Boolean, onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    val glow by animateFloatAsState(if (focused || active) 1f else 0f, label = "navGlow")
    Row(Modifier.fillMaxWidth().padding(vertical = 3.dp).clip(RoundedCornerShape(16.dp)).background(if (active) Color(0xFF1A0B10) else Color.Transparent).border(1.dp, TvRed.copy(alpha = glow), RoundedCornerShape(16.dp)).onFocusChanged { focused = it.isFocused }.focusable().clickable { onClick() }, verticalAlignment = Alignment.CenterVertically) {
        Text(icon, Modifier.padding(start = 13.dp), color = if (active || focused) TvRed else Color.White, fontSize = 20.sp)
        Text(label, Modifier.padding(horizontal = 13.dp, vertical = 12.dp), color = Color.White, fontSize = 13.sp, fontWeight = if (active || focused) FontWeight.Black else FontWeight.Bold)
    }
}

@Composable
private fun TvSportNavItem(sport: TvSport, onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    Row(Modifier.fillMaxWidth().padding(vertical = 2.dp).clip(RoundedCornerShape(12.dp)).background(if (focused) Color(0xFF111923) else Color.Transparent).border(1.dp, TvBlue.copy(alpha = if (focused) 1f else 0f), RoundedCornerShape(12.dp)).onFocusChanged { focused = it.isFocused }.focusable().clickable { onClick() }, verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(30.dp).padding(5.dp).clip(RoundedCornerShape(6.dp)).background(TvPanel2), contentAlignment = Alignment.Center) { Text(sport.glyph, color = if (focused) TvBlue else Color.White, fontSize = 7.sp, fontWeight = FontWeight.Black, textAlign = TextAlign.Center) }
        Text(sport.name, Modifier.padding(start = 9.dp, top = 7.dp, bottom = 7.dp), color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun TvTopBar(onConnect: () -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text("XSPORTSX", color = Color.White, fontSize = 17.sp, fontWeight = FontWeight.Black)
        Spacer(Modifier.weight(1f)); Text("⌕  Search", color = Color.White, fontSize = 15.sp, fontWeight = FontWeight.Bold); Spacer(Modifier.width(18.dp)); TvActionButton("⚙  Settings", onConnect); Spacer(Modifier.width(18.dp)); Text("TV MODE", color = TvMuted, fontSize = 10.sp, fontWeight = FontWeight.Black)
    }
}

@Composable
private fun TvActionButton(text: String, onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    Box(Modifier.clip(RoundedCornerShape(14.dp)).background(if (focused) Color(0xFF241018) else Color.Transparent).border(1.dp, TvRed.copy(alpha = if (focused) 1f else .35f), RoundedCornerShape(14.dp)).onFocusChanged { focused = it.isFocused }.focusable().clickable { onClick() }.padding(horizontal = 12.dp, vertical = 9.dp)) { Text(text, color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Bold) }
}

@Composable
private fun TvHero(onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    Box(Modifier.fillMaxWidth().height(160.dp).clip(RoundedCornerShape(18.dp)).background(Brush.horizontalGradient(listOf(Color(0xFF16090F), Color(0xFF101824), Color(0xFF08121D)))).border(1.dp, TvRed.copy(alpha = if (focused) 1f else .28f), RoundedCornerShape(18.dp)).onFocusChanged { focused = it.isFocused }.focusable().clickable { onClick() }) {
        Row(Modifier.fillMaxSize().padding(24.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("WELCOME TO", color = Color.White, fontSize = 12.sp, letterSpacing = 1.sp)
                Text("XSPORTSX", color = Color.White, fontSize = 34.sp, fontWeight = FontWeight.Black)
                Text("YOUR ULTIMATE SPORTS COMMAND CENTER", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(8.dp)); Text("REAL LIVE GAMES • LIVE SCORES • NETWORKS", color = TvMuted, fontSize = 10.sp, fontWeight = FontWeight.Bold)
            }
            Column(Modifier.width(220.dp).clip(RoundedCornerShape(16.dp)).background(Color(0xAA0A111A)).padding(16.dp)) {
                Text("LIVE SPORTS", color = TvRed, fontSize = 13.sp, fontWeight = FontWeight.Black)
                Text("No news photos or article cards in Live Now.\nOnly real-time game data appears below.", color = Color.White, fontSize = 11.sp, lineHeight = 19.sp)
            }
        }
    }
}

@Composable
private fun TvSection(title: String, action: String? = null) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) { Box(Modifier.size(8.dp).clip(RoundedCornerShape(50)).background(TvRed)); Spacer(Modifier.width(9.dp)); Text(title, color = Color.White, fontSize = 16.sp, fontWeight = FontWeight.Black, letterSpacing = 1.sp); Spacer(Modifier.weight(1f)); action?.let { Text(it, color = TvRed, fontSize = 11.sp, fontWeight = FontWeight.Bold) } }
    Spacer(Modifier.height(9.dp))
}

@Composable
private fun TvGameRow(games: List<TvGame>, onOpen: (String) -> Unit) {
    LazyRow(horizontalArrangement = Arrangement.spacedBy(14.dp), contentPadding = PaddingValues(bottom = 3.dp)) { items(games) { game -> TvGameCard(game) { onOpen(game.network) } } }
}

@Composable
private fun TvGameCard(game: TvGame, onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    Column(Modifier.width(205.dp).height(190.dp).clip(RoundedCornerShape(16.dp)).background(TvPanel).border(1.5.dp, TvRed.copy(alpha = if (focused) 1f else .25f), RoundedCornerShape(16.dp)).onFocusChanged { focused = it.isFocused }.focusable().clickable { onClick() }.padding(13.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) { Box(Modifier.clip(RoundedCornerShape(5.dp)).background(TvRed).padding(horizontal = 7.dp, vertical = 4.dp)) { Text("LIVE", color = Color.White, fontSize = 8.sp, fontWeight = FontWeight.Black) }; Spacer(Modifier.weight(1f)); Text(game.league, color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Bold) }
        Spacer(Modifier.height(15.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) { Text(game.home, color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.Black, maxLines = 1, overflow = TextOverflow.Ellipsis); Text("  VS  ", color = TvRed, fontSize = 9.sp, fontWeight = FontWeight.Black); Text(game.away, color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.Black, maxLines = 1, overflow = TextOverflow.Ellipsis) }
        Spacer(Modifier.height(12.dp)); Text(game.score, Modifier.fillMaxWidth(), color = Color.White, fontSize = 20.sp, fontWeight = FontWeight.Black, textAlign = TextAlign.Center); Spacer(Modifier.height(6.dp)); Text(game.status, Modifier.fillMaxWidth(), color = TvMuted, fontSize = 9.sp, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center); Spacer(Modifier.weight(1f)); Text(game.network, Modifier.fillMaxWidth(), color = Color.White, fontSize = 8.sp, fontWeight = FontWeight.Black, textAlign = TextAlign.Center)
    }
}

@Composable
private fun TvSportRow(sports: List<TvSport>, onOpen: (TvSport) -> Unit) {
    LazyRow(horizontalArrangement = Arrangement.spacedBy(12.dp), contentPadding = PaddingValues(bottom = 3.dp)) { items(sports) { sport -> TvSportCard(sport) { onOpen(sport) } } }
}

@Composable
private fun TvSportCard(sport: TvSport, onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    Column(Modifier.width(112.dp).height(100.dp).clip(RoundedCornerShape(13.dp)).background(TvPanel).border(1.5.dp, TvRed.copy(alpha = if (focused) 1f else .18f), RoundedCornerShape(13.dp)).onFocusChanged { focused = it.isFocused }.focusable().clickable { onClick() }, horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        Box(Modifier.size(42.dp).clip(RoundedCornerShape(10.dp)).background(if (focused) Color(0xFF241018) else TvPanel2), contentAlignment = Alignment.Center) { Text(sport.glyph, color = if (focused) TvRed else Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black, textAlign = TextAlign.Center) }
        Spacer(Modifier.height(8.dp)); Text(sport.name, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun TvNetworksBlock(onNetwork: (String) -> Unit) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(22.dp)) {
        Column(Modifier.weight(1f)) { TvSection("FEATURED NETWORKS"); LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) { items(tvNetworks.take(6)) { TvNetworkCard(it) { onNetwork(it.name) } } } }
        Column(Modifier.weight(1f)) { TvSection("COLLEGE NETWORKS"); LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) { items(tvNetworks.drop(6)) { TvNetworkCard(it) { onNetwork(it.name) } } } }
    }
}

@Composable
private fun TvNetworkGrid(networks: List<TvNetwork>, onNetwork: (String) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) { networks.chunked(5).forEach { row -> Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) { row.forEach { network -> TvNetworkCard(network) { onNetwork(network.name) } } } } }
}

@Composable
private fun TvNetworkCard(network: TvNetwork, onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    Column(Modifier.width(108.dp).height(72.dp).clip(RoundedCornerShape(11.dp)).background(TvPanel).border(1.5.dp, TvBlue.copy(alpha = if (focused) 1f else .16f), RoundedCornerShape(11.dp)).onFocusChanged { focused = it.isFocused }.focusable().clickable { onClick() }, horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        Text(network.mark, color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Black); Text(network.name, color = TvMuted, fontSize = 7.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

@Composable
private fun TvSettings(onConnect: () -> Unit) {
    TvSection("SETTINGS")
    Column(Modifier.widthIn(max = 700.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        TvSetting("Source connection", "Connect your authorized Xtream/M3U source", "CONNECT", onConnect)
        TvSetting("Device sync", "Pair this TV with your XSportsX mobile device", "PAIR", onConnect)
        TvSetting("TV controls", "D-pad optimized navigation and focus states", "ON", {})
    }
}

@Composable
private fun TvSetting(title: String, subtitle: String, action: String, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(15.dp)).background(TvPanel).padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) { Text(title, color = Color.White, fontWeight = FontWeight.Black); Text(subtitle, color = TvMuted, fontSize = 11.sp) }
        TvActionButton(action, onClick)
    }
}

@Composable
private fun TvEmpty(text: String) {
    Box(Modifier.fillMaxWidth().height(150.dp).clip(RoundedCornerShape(16.dp)).background(TvPanel), contentAlignment = Alignment.Center) { Text(text, color = TvMuted, fontSize = 13.sp, fontWeight = FontWeight.Bold) }
}
