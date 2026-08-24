package com.xsportsx.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.animation.AnimatedContent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { XSportsXApp() }
    }
}

data class Game(val league: String, val matchup: String, val time: String, val tag: String, val icon: String)

private val games = listOf(
    Game("NFL", "Dallas Cowboys vs Philadelphia Eagles", "Tonight • 8:20 PM", "LIVE SOON", "🏈"),
    Game("MLB", "Boston Red Sox vs Miami Marlins", "7:10 PM", "UPCOMING", "⚾"),
    Game("NHL", "Toronto Maple Leafs vs Montreal Canadiens", "7:00 PM", "UPCOMING", "🏒"),
    Game("UFC", "UFC Fight Night", "Saturday • 7:00 PM", "FIGHT NIGHT", "🥊"),
    Game("UFC", "Dana White's Contender Series", "Tuesday • 8:00 PM", "DWCS", "🥊"),
    Game("UFC", "Road to UFC", "Saturday", "ROAD TO UFC", "🥊"),
    Game("BOXING", "Championship Boxing", "Saturday", "BOXING", "🥊")
)

@Composable
fun XSportsXApp() {
    var tab by remember { mutableStateOf("HOME") }
    var selectedLeague by remember { mutableStateOf("ALL") }
    var selectedGame by remember { mutableStateOf<Game?>(null) }

    MaterialTheme(colorScheme = darkColorScheme(
        primary = Color(0xFFFF1744),
        secondary = Color(0xFFFF6D00),
        background = Color(0xFF07080C),
        surface = Color(0xFF10131A),
        surfaceVariant = Color(0xFF171B24)
    )) {
        Surface(modifier = Modifier.fillMaxSize(), color = Color(0xFF07080C)) {
            Row(Modifier.fillMaxSize()) {
                SideRail(tab) { tab = it }
                Box(Modifier.weight(1f).fillMaxHeight()) {
                    AnimatedContent(targetState = tab, label = "screen") { screen ->
                        when (screen) {
                            "HOME" -> HomeScreen(selectedLeague, { selectedLeague = it }) { selectedGame = it }
                            "LIVE" -> LiveScreen { selectedGame = it }
                            "SEARCH" -> SearchScreen { selectedGame = it }
                            "SOURCES" -> SourcesScreen()
                            "SETTINGS" -> SettingsScreen()
                        }
                    }
                }
            }
            selectedGame?.let { game -> EventSheet(game) { selectedGame = null } }
        }
    }
}

@Composable
fun SideRail(tab: String, onTab: (String) -> Unit) {
    Column(
        modifier = Modifier.width(88.dp).fillMaxHeight().background(Color(0xFF0B0D12)).padding(vertical = 22.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Box(Modifier.size(52.dp).clip(RoundedCornerShape(16.dp)).background(Brush.linearGradient(listOf(Color(0xFFFF1744), Color(0xFFFF6D00)))), contentAlignment = Alignment.Center) {
            Text("X", fontSize = 30.sp, fontWeight = FontWeight.Black, color = Color.White)
        }
        Spacer(Modifier.height(36.dp))
        listOf("🏠" to "HOME", "🔴" to "LIVE", "⌕" to "SEARCH", "▣" to "SOURCES", "⚙" to "SETTINGS").forEach { (icon, id) ->
            val active = tab == id
            Column(
                Modifier.padding(vertical = 7.dp).clip(RoundedCornerShape(18.dp)).background(if (active) Color(0xFF25121A) else Color.Transparent).clickable { onTab(id) }.padding(horizontal = 12.dp, vertical = 10.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(icon, fontSize = 22.sp)
                Text(id.lowercase().replaceFirstChar { it.uppercase() }, fontSize = 9.sp, color = if (active) Color.White else Color(0xFF777D89))
            }
        }
        Spacer(Modifier.weight(1f))
        Text("1.0", color = Color(0xFF555A66), fontSize = 10.sp)
    }
}

@Composable
fun Header(title: String, subtitle: String? = null) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 34.dp, vertical = 24.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(title, fontSize = 30.sp, fontWeight = FontWeight.Black, color = Color.White)
            subtitle?.let { Text(it, color = Color(0xFF858B98), fontSize = 13.sp) }
        }
        Box(Modifier.clip(RoundedCornerShape(22.dp)).background(Color(0xFF11151D)).padding(horizontal = 16.dp, vertical = 9.dp)) {
            Text("●  XSPORTSX", color = Color(0xFFFF3D5A), fontWeight = FontWeight.Bold, fontSize = 11.sp)
        }
    }
}

@Composable
fun HomeScreen(league: String, onLeague: (String) -> Unit, onGame: (Game) -> Unit) {
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 40.dp)) {
        item {
            Header("SPORTS COMMAND CENTER", "Live events, upcoming fights and your connected TV sources")
            HeroBanner { onGame(games[4]) }
            LeagueChips(league, onLeague)
        }
        item { SectionTitle(if (league == "ALL") "FEATURED EVENTS" else league) }
        val filtered = if (league == "ALL") games else games.filter { it.league == league }
        item { GameRow(filtered, onGame) }
        item { SectionTitle("COMBAT SPORTS") }
        item { GameRow(games.filter { it.league == "UFC" || it.league == "BOXING" }, onGame) }
        item { SectionTitle("ALL SPORTS") }
        item { GameRow(games.take(4), onGame) }
    }
}

@Composable
fun HeroBanner(onClick: () -> Unit) {
    Box(Modifier.padding(horizontal = 34.dp).fillMaxWidth().height(210.dp).clip(RoundedCornerShape(28.dp)).clickable { onClick() }.background(Brush.linearGradient(listOf(Color(0xFF260913), Color(0xFF121722), Color(0xFF321306))))) {
        Column(Modifier.padding(28.dp).align(Alignment.CenterStart)) {
            Text("LIVE SPORTS", color = Color(0xFFFF1744), fontWeight = FontWeight.Black, letterSpacing = 2.sp)
            Text("THE GAME IS ON.", color = Color.White, fontSize = 34.sp, fontWeight = FontWeight.Black)
            Text("One app. Every league. Your authorized sources.", color = Color(0xFFB6BBC5), fontSize = 14.sp)
            Spacer(Modifier.height(16.dp))
            Box(Modifier.clip(RoundedCornerShape(14.dp)).background(Color(0xFFFF1744)).padding(horizontal = 18.dp, vertical = 10.dp)) { Text("BROWSE LIVE →", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 12.sp) }
        }
        Text("⚡", Modifier.align(Alignment.CenterEnd).padding(end = 60.dp), fontSize = 92.sp)
    }
}

@Composable
fun LeagueChips(selected: String, onSelect: (String) -> Unit) {
    val leagues = listOf("ALL", "NFL", "NBA", "NCAA", "MLB", "NHL", "UFC", "BOXING", "SOCCER")
    LazyRow(contentPadding = PaddingValues(horizontal = 34.dp, vertical = 22.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        items(leagues) { l ->
            FilterChip(selected = selected == l, onClick = { onSelect(l) }, label = { Text(l, fontWeight = FontWeight.Bold) })
        }
    }
}

@Composable fun SectionTitle(text: String) { Text(text, Modifier.padding(start = 34.dp, top = 12.dp, bottom = 12.dp), color = Color.White, fontSize = 16.sp, fontWeight = FontWeight.Black, letterSpacing = 1.5.sp) }

@Composable
fun GameRow(list: List<Game>, onGame: (Game) -> Unit) {
    LazyRow(contentPadding = PaddingValues(horizontal = 34.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
        items(list) { game -> GameCard(game, onGame) }
    }
}

@Composable
fun GameCard(game: Game, onGame: (Game) -> Unit) {
    Column(Modifier.width(255.dp).clip(RoundedCornerShape(22.dp)).background(Color(0xFF11151D)).clickable { onGame(game) }) {
        Box(Modifier.fillMaxWidth().height(130.dp).background(Brush.linearGradient(listOf(Color(0xFF242832), Color(0xFF0F1116)))), contentAlignment = Alignment.Center) {
            Text(game.icon, fontSize = 58.sp)
            Box(Modifier.align(Alignment.TopStart).padding(12.dp).clip(RoundedCornerShape(8.dp)).background(if (game.tag == "LIVE") Color(0xFFFF1744) else Color(0xAA000000)).padding(horizontal = 8.dp, vertical = 5.dp)) { Text(game.tag, color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Black) }
        }
        Column(Modifier.padding(15.dp)) {
            Text(game.league, color = Color(0xFFFF536C), fontSize = 10.sp, fontWeight = FontWeight.Black, letterSpacing = 1.sp)
            Text(game.matchup, color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Bold, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Spacer(Modifier.height(7.dp))
            Text(game.time, color = Color(0xFF8D94A2), fontSize = 11.sp)
        }
    }
}

@Composable
fun LiveScreen(onGame: (Game) -> Unit) {
    Column(Modifier.fillMaxSize()) {
        Header("LIVE NOW", "Streams become available when your connected source matches the event")
        val live = games.filter { it.league == "NFL" || it.league == "MLB" }
        if (live.isEmpty()) EmptyState("Nothing live right now") else LazyColumn(contentPadding = PaddingValues(34.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) { items(live) { LiveRow(it, onGame) } }
    }
}

@Composable fun LiveRow(game: Game, onGame: (Game) -> Unit) { Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Color(0xFF11151D)).clickable { onGame(game) }.padding(18.dp), verticalAlignment = Alignment.CenterVertically) { Text(game.icon, fontSize = 34.sp); Spacer(Modifier.width(18.dp)); Column(Modifier.weight(1f)) { Text(game.matchup, color = Color.White, fontWeight = FontWeight.Bold); Text(game.league + " • " + game.time, color = Color(0xFF8B919D), fontSize = 12.sp) }; Text("WATCH →", color = Color(0xFFFF1744), fontWeight = FontWeight.Black, fontSize = 11.sp) } }

@Composable
fun SearchScreen(onGame: (Game) -> Unit) {
    var query by remember { mutableStateOf("") }
    val results = games.filter { query.isBlank() || (it.matchup + it.league + it.tag).contains(query, ignoreCase = true) }
    Column(Modifier.fillMaxSize()) {
        Header("SEARCH SPORTS", "Find teams, fighters, leagues and events")
        OutlinedTextField(query, { query = it }, Modifier.fillMaxWidth().padding(horizontal = 34.dp), placeholder = { Text("Search Cowboys, UFC, boxing…") }, singleLine = true)
        LazyColumn(contentPadding = PaddingValues(34.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) { items(results) { LiveRow(it, onGame) } }
    }
}

@Composable
fun SourcesScreen() {
    var host by remember { mutableStateOf("") }; var user by remember { mutableStateOf("") }; var pass by remember { mutableStateOf("") }; var saved by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxSize()) {
        Header("SOURCE CENTER", "Connect your authorized Xtream Codes or M3U source")
        Column(Modifier.padding(horizontal = 34.dp).widthIn(max = 720.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("XTREAM CODES", color = Color(0xFFFF536C), fontWeight = FontWeight.Black, letterSpacing = 1.5.sp)
            OutlinedTextField(host, { host = it }, Modifier.fillMaxWidth(), label = { Text("Server URL") }, placeholder = { Text("https://provider.example") }, singleLine = true)
            OutlinedTextField(user, { user = it }, Modifier.fillMaxWidth(), label = { Text("Username") }, singleLine = true)
            OutlinedTextField(pass, { pass = it }, Modifier.fillMaxWidth(), label = { Text("Password") }, singleLine = true)
            Button(onClick = { saved = true }, Modifier.fillMaxWidth().height(52.dp), shape = RoundedCornerShape(14.dp)) { Text(if (saved) "SOURCE SAVED ✓" else "CONNECT SOURCE", fontWeight = FontWeight.Black) }
            Text("Credentials are kept on-device in the production build. Stream discovery only uses the source you connect.", color = Color(0xFF737A87), fontSize = 12.sp)
        }
    }
}

@Composable
fun SettingsScreen() { Column(Modifier.fillMaxSize()) { Header("SETTINGS", "Make XSportsX yours") ; SettingRow("Auto refresh", "Keep schedules and source matches current", true); SettingRow("Live alerts", "Notify when a selected event is available", true); SettingRow("TV mode", "Optimize controls and focus for Android TV", true); SettingRow("Theme", "Obsidian / Red", false) } }

@Composable fun SettingRow(title: String, subtitle: String, checked: Boolean) { Row(Modifier.fillMaxWidth().padding(horizontal = 34.dp, vertical = 8.dp).clip(RoundedCornerShape(18.dp)).background(Color(0xFF11151D)).padding(18.dp), verticalAlignment = Alignment.CenterVertically) { Column(Modifier.weight(1f)) { Text(title, color = Color.White, fontWeight = FontWeight.Bold); Text(subtitle, color = Color(0xFF7D8491), fontSize = 12.sp) }; Switch(checked, {}) } }

@Composable fun EmptyState(text: String) { Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Column(horizontalAlignment = Alignment.CenterHorizontally) { Text("◉", fontSize = 48.sp, color = Color(0xFF333944)); Text(text, color = Color(0xFF858B98), fontSize = 16.sp, fontWeight = FontWeight.Bold) } } }

@Composable
fun EventSheet(game: Game, onClose: () -> Unit) {
    Box(Modifier.fillMaxSize().background(Color(0x99000000)), contentAlignment = Alignment.BottomCenter) {
        Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(topStart = 30.dp, topEnd = 30.dp)).background(Color(0xFF10131A)).padding(28.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) { Text(game.icon, fontSize = 42.sp); Spacer(Modifier.width(16.dp)); Column(Modifier.weight(1f)) { Text(game.matchup, color = Color.White, fontSize = 21.sp, fontWeight = FontWeight.Black); Text(game.league + " • " + game.time, color = Color(0xFF8A919E)) }; TextButton(onClick = onClose) { Text("CLOSE") } }
            Spacer(Modifier.height(22.dp))
            Text("SOURCE MATCHING", color = Color(0xFFFF536C), fontWeight = FontWeight.Black, letterSpacing = 1.2.sp)
            Text("XSportsX will search your connected Xtream/M3U source using team/fighter names, aliases, league and event metadata.", color = Color(0xFF9AA1AE), fontSize = 13.sp)
            Spacer(Modifier.height(18.dp))
            Button(onClick = { }, Modifier.fillMaxWidth().height(52.dp), shape = RoundedCornerShape(15.dp)) { Text("FIND AVAILABLE STREAMS", fontWeight = FontWeight.Black) }
        }
    }
}
