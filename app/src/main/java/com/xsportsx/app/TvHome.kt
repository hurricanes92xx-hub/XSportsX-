package com.xsportsx.app

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
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
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil3.compose.AsyncImage
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
    val homeLogo: String,
    val awayLogo: String,
    val score: String,
    val status: String,
    val network: String,
    val live: Boolean,
    val timestamp: Long
)
private data class TvSport(val name: String, val glyph: String)
private data class TvNetwork(val name: String, val mark: String)
data class TvLeague(val name: String, val sport: String, val id: String)

val liveLeagues = listOf(
    TvLeague("NFL", "football", "nfl"), TvLeague("NCAA FB", "football", "college-football"),
    TvLeague("NBA", "basketball", "nba"), TvLeague("WNBA", "basketball", "wnba"),
    TvLeague("NCAA BB", "basketball", "mens-college-basketball"), TvLeague("MLB", "baseball", "mlb"),
    TvLeague("NHL", "hockey", "nhl"), TvLeague("MLS", "soccer", "usa.1"), TvLeague("EPL", "soccer", "eng.1")
)

private val tvSports = listOf(
    TvSport("NFL", "NFL"), TvSport("NBA", "NBA"), TvSport("NCAA FB", "NCAA"), TvSport("NCAA BB", "NCAA"),
    TvSport("MLB", "MLB"), TvSport("NHL", "NHL"), TvSport("UFC", "UFC"), TvSport("BOXING", "BOX")
)

private val tvNetworks = listOf(
    TvNetwork("ESPN", "ESPN"), TvNetwork("ESPN2", "ESPN2"), TvNetwork("ESPNU", "ESPNU"),
    TvNetwork("NFL NETWORK", "NFL"), TvNetwork("FS1", "FS1"), TvNetwork("CBS SPORTS", "CBS"),
    TvNetwork("SEC NETWORK", "SEC"), TvNetwork("ACC NETWORK", "ACC"), TvNetwork("BIG TEN NETWORK", "B1G"), TvNetwork("ESPN+", "ESPN+")
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
        c.connectTimeout = 3000; c.readTimeout = 5000; c.requestMethod = "GET"
        c.setRequestProperty("User-Agent", "XSportsX/1.6"); c.setRequestProperty("Accept", "application/json")
        if (c.responseCode !in 200..299) null else c.inputStream.bufferedReader().use { JSONObject(it.readText()) }
    } catch (_: Exception) { null } finally { c.disconnect() }
}

private fun eventMillis(event: JSONObject): Long = try { java.time.Instant.parse(event.optString("date")).toEpochMilli() } catch (_: Exception) { 0L }

private suspend fun loadTvGames(): List<TvGame> = withContext(Dispatchers.IO) {
    liveLeagues.flatMap { league ->
        val url = "https://site.api.espn.com/apis/site/v2/sports/${league.sport}/${league.id}/scoreboard?dates=${dateRange()}&limit=50"
        val events = tvJson(url)?.optJSONArray("events") ?: return@flatMap emptyList()
        buildList {
            for (i in 0 until events.length()) {
                val event = events.optJSONObject(i) ?: continue
                val competition = event.optJSONArray("competitions")?.optJSONObject(0) ?: continue
                val status = competition.optJSONObject("status")?.optJSONObject("type") ?: continue
                if (status.optString("state") != "in") continue
                val competitors = competition.optJSONArray("competitors") ?: continue
                var home = "TBD"; var away = "TBD"; var homeScore = "0"; var awayScore = "0"
                var homeLogo = ""; var awayLogo = ""
                for (j in 0 until competitors.length()) {
                    val team = competitors.optJSONObject(j) ?: continue
                    val teamObj = team.optJSONObject("team") ?: continue
                    val name = teamObj.optString("abbreviation").ifBlank { teamObj.optString("shortDisplayName") }.ifBlank { "TBD" }
                    val score = team.optString("score").ifBlank { "0" }
                    val logo = teamObj.optJSONArray("logos")?.optJSONObject(0)?.optString("href").orEmpty()
                    if (team.optString("homeAway") == "home") { home = name; homeScore = score; homeLogo = logo }
                    else { away = name; awayScore = score; awayLogo = logo }
                }
                val detail = status.optString("shortDetail").ifBlank { status.optString("detail") }.ifBlank { "LIVE" }
                val network = competition.optJSONArray("broadcasts")?.optJSONObject(0)?.optJSONArray("names")?.optString(0).orEmpty().ifBlank { "LIVE" }
                add(TvGame(league.name, home, away, homeLogo, awayLogo, "$awayScore  •  $homeScore", detail, network, true, eventMillis(event)))
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
        TvGlowingCracks(Modifier.fillMaxSize())
        Row(Modifier.fillMaxSize()) {
            TvNav(selectedNav) { selectedNav = it }
            Column(Modifier.weight(1f).fillMaxHeight().verticalScroll(scroll).padding(start = 22.dp, end = 30.dp, top = 20.dp, bottom = 76.dp)) {
                TvTopBar(onConnect); Spacer(Modifier.height(14.dp))
                when (selectedNav) {
                    "HOME" -> { TvHero(onConnect); Spacer(Modifier.height(18.dp)); TvSection("LIVE NOW", if (liveGames.isEmpty()) "Waiting for live scores" else "${liveGames.size} LIVE"); if (liveGames.isNotEmpty()) TvGameRow(liveGames, onNetwork) else TvLiveEmpty(loadingLive); Spacer(Modifier.height(16.dp)); TvSection("TOP SPORTS"); TvSportRow(tvSports) { sport -> onNetwork(sport.name) }; Spacer(Modifier.height(16.dp)); TvNetworksBlock(onNetwork) }
                    "LIVE NOW" -> { TvSection("LIVE NOW", if (liveGames.isEmpty()) "No games live right now" else "${liveGames.size} LIVE"); if (liveGames.isNotEmpty()) TvGameRow(liveGames, onNetwork) else TvLiveEmpty(loadingLive) }
                    "UPCOMING" -> { TvSection("UPCOMING"); TvEmpty("Upcoming events will appear here") }
                    "NETWORKS" -> { TvSection("SPORTS NETWORKS"); TvNetworkGrid(tvNetworks, onNetwork) }
                    "FAVORITES" -> { TvSection("FAVORITES"); TvEmpty("Your favorite leagues and networks will appear here") }
                    "SETTINGS" -> TvSettings(onConnect)
                }
            }
        }
        HomeSportsTicker(Modifier.align(Alignment.BottomCenter).fillMaxWidth())
    }
}

@Composable private fun TvLiveEmpty(loading: Boolean) {
    Box(Modifier.fillMaxWidth().height(170.dp).clip(RoundedCornerShape(16.dp)).background(TvPanel).border(1.dp, TvRed.copy(alpha = .18f), RoundedCornerShape(16.dp)), contentAlignment = Alignment.Center) { Column(horizontalAlignment = Alignment.CenterHorizontally) { Text(if (loading) "LOADING LIVE GAMES…" else "NO LIVE GAMES RIGHT NOW", color = Color.White, fontSize = 15.sp, fontWeight = FontWeight.Black); Text("Live scores refresh automatically", color = TvMuted, fontSize = 10.sp) } }
}

@Composable private fun TvNav(selected: String, onSelect: (String) -> Unit) {
    Column(Modifier.width(210.dp).fillMaxHeight().background(Brush.horizontalGradient(listOf(Color(0xFF071019), Color(0xFF04070C)))).padding(start = 22.dp, top = 22.dp, end = 18.dp, bottom = 72.dp)) {
        Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.CenterStart) { XtremeLogo(size = 72.dp) }
        Spacer(Modifier.height(30.dp)); listOf("⌂" to "HOME", "●" to "LIVE NOW", "▣" to "UPCOMING", "▤" to "NETWORKS", "★" to "FAVORITES", "⚙" to "SETTINGS").forEach { (icon, label) -> TvNavItem(icon, label, selected == label) { onSelect(label) } }
        Spacer(Modifier.height(22.dp)); Text("SPORTS", color = TvMuted, fontSize = 9.sp, fontWeight = FontWeight.Black, letterSpacing = 1.4.sp); Spacer(Modifier.height(6.dp)); tvSports.forEach { sport -> TvSportNavItem(sport) { onSelect(sport.name) } }
        Spacer(Modifier.weight(1f)); Text("XSportsX TV", color = Color(0xFF596371), fontSize = 10.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable private fun TvNavItem(icon: String, label: String, active: Boolean, onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }; val glow by animateFloatAsState(if (focused || active) 1f else 0f, label = "navGlow")
    Row(Modifier.fillMaxWidth().padding(vertical = 3.dp).clip(RoundedCornerShape(16.dp)).background(if (active) Color(0xFF1A0B10) else Color.Transparent).border(1.dp, TvRed.copy(alpha = glow), RoundedCornerShape(16.dp)).onFocusChanged { focused = it.isFocused }.focusable().clickable { onClick() }, verticalAlignment = Alignment.CenterVertically) { Text(icon, Modifier.padding(start = 13.dp), color = if (active || focused) TvRed else Color.White, fontSize = 20.sp); Text(label, Modifier.padding(horizontal = 13.dp, vertical = 12.dp), color = Color.White, fontSize = 13.sp, fontWeight = if (active || focused) FontWeight.Black else FontWeight.Bold) }
}

@Composable private fun TvSportNavItem(sport: TvSport, onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    Row(Modifier.fillMaxWidth().padding(vertical = 2.dp).clip(RoundedCornerShape(12.dp)).background(if (focused) Color(0xFF111923) else Color.Transparent).border(1.dp, TvBlue.copy(alpha = if (focused) 1f else 0f), RoundedCornerShape(12.dp)).onFocusChanged { focused = it.isFocused }.focusable().clickable { onClick() }, verticalAlignment = Alignment.CenterVertically) {
        TvSportMark(sport.name, 30.dp, focused); Text(sport.name, Modifier.padding(start = 9.dp, top = 7.dp, bottom = 7.dp), color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable private fun TvTopBar(onConnect: () -> Unit) { Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) { XtremeLogo(size = 56.dp); Spacer(Modifier.weight(1f)); Text("⌕  Search", color = Color.White, fontSize = 15.sp, fontWeight = FontWeight.Bold); Spacer(Modifier.width(18.dp)); TvActionButton("⚙  Settings", onConnect); Spacer(Modifier.width(18.dp)); Text("TV MODE", color = TvMuted, fontSize = 10.sp, fontWeight = FontWeight.Black) } }

@Composable private fun TvActionButton(text: String, onClick: () -> Unit) { var focused by remember { mutableStateOf(false) }; Box(Modifier.clip(RoundedCornerShape(14.dp)).background(if (focused) Color(0xFF241018) else Color.Transparent).border(1.dp, TvRed.copy(alpha = if (focused) 1f else .35f), RoundedCornerShape(14.dp)).onFocusChanged { focused = it.isFocused }.focusable().clickable { onClick() }.padding(horizontal = 12.dp, vertical = 9.dp)) { Text(text, color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Bold) } }

@Composable private fun TvHero(onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    Box(Modifier.fillMaxWidth().height(160.dp).clip(RoundedCornerShape(18.dp)).background(Brush.horizontalGradient(listOf(Color(0xFF16090F), Color(0xFF101824), Color(0xFF08121D)))).border(1.dp, TvRed.copy(alpha = if (focused) 1f else .28f), RoundedCornerShape(18.dp)).onFocusChanged { focused = it.isFocused }.focusable().clickable { onClick() }) {
        Row(Modifier.fillMaxSize().padding(24.dp), verticalAlignment = Alignment.CenterVertically) { Column(Modifier.weight(1f)) { Text("WELCOME TO", color = Color.White, fontSize = 12.sp, letterSpacing = 1.sp); Text("XSPORTSX", color = Color.White, fontSize = 34.sp, fontWeight = FontWeight.Black); Text("YOUR ULTIMATE SPORTS COMMAND CENTER", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Bold); Spacer(Modifier.height(8.dp)); Text("REAL LIVE GAMES • LIVE SCORES • NETWORKS", color = TvMuted, fontSize = 10.sp, fontWeight = FontWeight.Bold) }; Column(Modifier.width(220.dp).clip(RoundedCornerShape(16.dp)).background(Color(0xAA0A111A)).padding(16.dp)) { Text("LIVE SPORTS", color = TvRed, fontSize = 13.sp, fontWeight = FontWeight.Black); Text("No news photos or article cards in Live Now.\nOnly real-time game data appears below.", color = Color.White, fontSize = 11.sp, lineHeight = 19.sp) } }
    }
}

@Composable private fun TvSection(title: String, action: String? = null) { Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) { Box(Modifier.size(8.dp).clip(RoundedCornerShape(50)).background(TvRed)); Spacer(Modifier.width(9.dp)); Text(title, color = Color.White, fontSize = 16.sp, fontWeight = FontWeight.Black, letterSpacing = 1.sp); Spacer(Modifier.weight(1f)); action?.let { Text(it, color = TvRed, fontSize = 11.sp, fontWeight = FontWeight.Bold) } }; Spacer(Modifier.height(9.dp)) }

@Composable private fun TvGameRow(games: List<TvGame>, onOpen: (String) -> Unit) { LazyRow(horizontalArrangement = Arrangement.spacedBy(14.dp), contentPadding = PaddingValues(bottom = 3.dp)) { items(games) { game -> TvGameCard(game) { onOpen(game.network) } } } }

@Composable private fun TvGameCard(game: TvGame, onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    Column(Modifier.width(205.dp).height(190.dp).clip(RoundedCornerShape(16.dp)).background(TvPanel).border(1.5.dp, TvRed.copy(alpha = if (focused) 1f else .25f), RoundedCornerShape(16.dp)).onFocusChanged { focused = it.isFocused }.focusable().clickable { onClick() }.padding(13.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) { Box(Modifier.clip(RoundedCornerShape(5.dp)).background(TvRed).padding(horizontal = 7.dp, vertical = 4.dp)) { Text("LIVE", color = Color.White, fontSize = 8.sp, fontWeight = FontWeight.Black) }; Spacer(Modifier.weight(1f)); Text(game.league, color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Bold) }
        Spacer(Modifier.height(11.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
            TvTeamLogo(game.homeLogo, game.home, 42.dp)
            Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(horizontal = 7.dp)) { Text("VS", color = TvRed, fontSize = 9.sp, fontWeight = FontWeight.Black); Text(game.league, color = TvMuted, fontSize = 6.sp, fontWeight = FontWeight.Black) }
            TvTeamLogo(game.awayLogo, game.away, 42.dp)
        }
        Spacer(Modifier.height(7.dp)); Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) { Text(game.home, color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Black, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.width(70.dp), textAlign = TextAlign.Center); Text(game.away, color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Black, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.width(70.dp), textAlign = TextAlign.Center) }
        Spacer(Modifier.height(8.dp)); Text(game.score, Modifier.fillMaxWidth(), color = Color.White, fontSize = 19.sp, fontWeight = FontWeight.Black, textAlign = TextAlign.Center); Spacer(Modifier.height(5.dp)); Text(game.status, Modifier.fillMaxWidth(), color = TvMuted, fontSize = 9.sp, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center); Spacer(Modifier.weight(1f)); Text(game.network, Modifier.fillMaxWidth(), color = Color.White, fontSize = 8.sp, fontWeight = FontWeight.Black, textAlign = TextAlign.Center)
    }
}

@Composable private fun TvTeamLogo(url: String, name: String, size: androidx.compose.ui.unit.Dp) {
    Box(Modifier.size(size).clip(CircleShape).background(Brush.radialGradient(listOf(Color(0xFF202A38), Color(0xFF0A0E15)))), contentAlignment = Alignment.Center) {
        Text(teamMark(name), color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.Black, textAlign = TextAlign.Center)
        if (url.isNotBlank()) AsyncImage(model = url, contentDescription = name, modifier = Modifier.fillMaxSize().padding(5.dp), contentScale = ContentScale.Fit)
    }
}

@Composable private fun TvSportRow(sports: List<TvSport>, onOpen: (TvSport) -> Unit) { LazyRow(horizontalArrangement = Arrangement.spacedBy(12.dp), contentPadding = PaddingValues(bottom = 3.dp)) { items(sports) { sport -> TvSportCard(sport) { onOpen(sport) } } } }

@Composable private fun TvSportCard(sport: TvSport, onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    Column(Modifier.width(112.dp).height(100.dp).clip(RoundedCornerShape(13.dp)).background(TvPanel).border(1.5.dp, TvRed.copy(alpha = if (focused) 1f else .18f), RoundedCornerShape(13.dp)).onFocusChanged { focused = it.isFocused }.focusable().clickable { onClick() }, horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        TvSportMark(sport.name, 42.dp, focused); Spacer(Modifier.height(8.dp)); Text(sport.name, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable private fun TvSportMark(name: String, size: androidx.compose.ui.unit.Dp, focused: Boolean) {
    val key = name.uppercase()
    val (label, fg, bg) = when {
        key == "NFL" -> Triple("NFL", Color.White, Color(0xFF102B52))
        key == "NBA" -> Triple("NBA", Color.White, Color(0xFF8B1736))
        key == "NCAA FB" -> Triple("NCAA", Color.White, Color(0xFF6A1515))
        key == "NCAA BB" -> Triple("NCAA", Color.White, Color(0xFF173B67))
        key == "MLB" -> Triple("MLB", Color.White, Color(0xFF173C73))
        key == "NHL" -> Triple("NHL", Color.White, Color(0xFF202A38))
        key == "UFC" -> Triple("UFC", Color.White, Color(0xFF7A0F22))
        key == "BOXING" || key == "BOX" -> Triple("BOX", Color.White, Color(0xFF3A1B10))
        else -> Triple(key.take(5), Color.White, Color(0xFF202A38))
    }
    Box(Modifier.size(size).clip(RoundedCornerShape(size / 4)).background(if (focused) Color(0xFF241018) else bg).border(1.dp, if (focused) TvRed else Color(0xFF273445), RoundedCornerShape(size / 4)), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(label, color = if (focused) TvRed else fg, fontSize = if (label.length > 4) (size.value * .17f).sp else (size.value * .23f).sp, fontWeight = FontWeight.Black, letterSpacing = .3.sp)
            if (size.value >= 40f) Text(when (key) { "NFL" -> "FOOTBALL"; "NBA" -> "BASKETBALL"; "MLB" -> "BASEBALL"; "NHL" -> "HOCKEY"; "UFC" -> "FIGHT"; "BOXING" -> "COMBAT"; else -> "SPORTS" }, color = Color.White.copy(alpha = .62f), fontSize = 5.sp, fontWeight = FontWeight.Bold, letterSpacing = .6.sp)
        }
    }
}

@Composable private fun TvNetworksBlock(onNetwork: (String) -> Unit) { Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(22.dp)) { Column(Modifier.weight(1f)) { TvSection("FEATURED NETWORKS"); LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) { items(tvNetworks.take(6)) { TvNetworkCard(it) { onNetwork(it.name) } } } }; Column(Modifier.weight(1f)) { TvSection("COLLEGE NETWORKS"); LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) { items(tvNetworks.drop(6)) { TvNetworkCard(it) { onNetwork(it.name) } } } } } }
@Composable private fun TvNetworkGrid(networks: List<TvNetwork>, onNetwork: (String) -> Unit) { Column(verticalArrangement = Arrangement.spacedBy(12.dp)) { networks.chunked(5).forEach { row -> Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) { row.forEach { network -> TvNetworkCard(network) { onNetwork(network.name) } } } } } }
@Composable private fun TvNetworkCard(network: TvNetwork, onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    Column(Modifier.width(108.dp).height(86.dp).clip(RoundedCornerShape(11.dp)).background(TvPanel).border(1.5.dp, TvBlue.copy(alpha = if (focused) 1f else .16f), RoundedCornerShape(11.dp)).onFocusChanged { focused = it.isFocused }.focusable().clickable { onClick() }, horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        TvNetworkMark(network.name, network.mark, 42.dp, focused)
        Spacer(Modifier.height(5.dp))
        Text(network.name, color = Color.White, fontSize = 7.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

@Composable private fun TvNetworkMark(name: String, mark: String, size: androidx.compose.ui.unit.Dp, focused: Boolean) {
    val key = name.uppercase()
    val (label, bg, fg) = when {
        key == "ESPN" -> Triple("ESPN", Color(0xFF181818), Color(0xFFFF303F))
        key == "ESPN2" -> Triple("ESPN2", Color(0xFF181818), Color(0xFFFF303F))
        key == "ESPNU" -> Triple("ESPNU", Color(0xFF181818), Color(0xFFFF303F))
        key == "NFL NETWORK" -> Triple("NFL", Color(0xFF102B52), Color.White)
        key == "FS1" -> Triple("FS1", Color(0xFF173A6A), Color.White)
        key == "CBS SPORTS" -> Triple("CBS", Color(0xFF123C63), Color.White)
        key == "SEC NETWORK" -> Triple("SEC", Color(0xFF1B3158), Color.White)
        key == "ACC NETWORK" -> Triple("ACC", Color(0xFF15548B), Color.White)
        key == "BIG TEN NETWORK" -> Triple("B1G", Color(0xFF24374D), Color.White)
        key == "ESPN+" -> Triple("ESPN+", Color(0xFF181818), Color(0xFFFF303F))
        else -> Triple(mark, Color(0xFF202A38), Color.White)
    }
    Box(Modifier.size(size).clip(RoundedCornerShape(size / 4)).background(if (focused) Color(0xFF241018) else bg).border(1.dp, if (focused) TvRed else Color(0xFF273445), RoundedCornerShape(size / 4)), contentAlignment = Alignment.Center) {
        Text(label, color = if (focused) TvRed else fg, fontSize = if (label.length > 4) 8.sp else 11.sp, fontWeight = FontWeight.Black, letterSpacing = .25.sp, textAlign = TextAlign.Center)
    }
}

@Composable private fun TvSettings(onConnect: () -> Unit) { TvSection("SETTINGS"); Column(Modifier.widthIn(max = 700.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) { TvSetting("Source connection", "Connect your authorized Xtream/M3U source", "CONNECT", onConnect); TvSetting("Device sync", "Pair this TV with your XSportsX mobile device", "PAIR", onConnect); TvSetting("TV controls", "D-pad optimized navigation and focus states", "ON", {}) } }
@Composable private fun TvSetting(title: String, subtitle: String, action: String, onClick: () -> Unit) { Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(15.dp)).background(TvPanel).padding(16.dp), verticalAlignment = Alignment.CenterVertically) { Column(Modifier.weight(1f)) { Text(title, color = Color.White, fontWeight = FontWeight.Black); Text(subtitle, color = TvMuted, fontSize = 11.sp) }; TvActionButton(action, onClick) } }
@Composable fun TvEmpty(text: String) { Box(Modifier.fillMaxWidth().height(150.dp).clip(RoundedCornerShape(16.dp)).background(TvPanel), contentAlignment = Alignment.Center) { Text(text, color = TvMuted, fontSize = 13.sp, fontWeight = FontWeight.Bold) } }

private fun teamMark(name: String): String = name.trim().split(Regex("\\s+")).filter { it.isNotBlank() }.take(2).joinToString("") { it.take(1).uppercase() }.ifBlank { "•" }


@Composable
private fun TvGlowingCracks(modifier: Modifier) {
    Canvas(modifier) {
        val w = size.width
        val h = size.height
        val lines = listOf(
            listOf(.00f to .20f, .11f to .25f, .16f to .34f, .29f to .38f),
            listOf(1.00f to .17f, .88f to .24f, .83f to .34f, .69f to .40f),
            listOf(.03f to .77f, .16f to .72f, .23f to .61f, .37f to .57f),
            listOf(.97f to .73f, .85f to .67f, .79f to .56f, .64f to .51f),
            listOf(.43f to .00f, .47f to .10f, .53f to .18f, .60f to .27f)
        )
        lines.forEach { points ->
            for (i in 0 until points.lastIndex) {
                val a = points[i]
                val b = points[i + 1]
                val start = androidx.compose.ui.geometry.Offset(a.first * w, a.second * h)
                val end = androidx.compose.ui.geometry.Offset(b.first * w, b.second * h)
                drawLine(TvRed.copy(alpha = .10f), start, end, strokeWidth = 24f)
                drawLine(TvRed.copy(alpha = .20f), start, end, strokeWidth = 10f)
                drawLine(TvRed.copy(alpha = .72f), start, end, strokeWidth = 3f)
            }
        }
    }
}
