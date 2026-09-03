package com.xsportsx.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.animation.AnimatedContent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTag
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import kotlinx.coroutines.delay
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { XSportsXApp() }
    }
}

@Composable
fun XSportsXApp() {
    var tab by remember { mutableStateOf("HOME") }
    var selectedLeague by remember { mutableStateOf("ALL") }
    var selectedEvent by remember { mutableStateOf<SportsEvent?>(null) }
    var playingStream by remember { mutableStateOf<ResolvedStream?>(null) }

    MaterialTheme(colorScheme = darkColorScheme(
        primary = Color(0xFFFF1744), secondary = Color(0xFFFF6D00),
        background = Color(0xFF07080C), surface = Color(0xFF10131A), surfaceVariant = Color(0xFF171B24)
    )) {
        Surface(
            modifier = Modifier.fillMaxSize().safeDrawingPadding().semantics { testTagsAsResourceId = true },
            color = Color(0xFF07080C)
        ) {
            if (playingStream != null) {
                NativePlayerScreen(playingStream!!.url, playingStream!!.name) { playingStream = null }
            } else {
                Row(Modifier.fillMaxSize()) {
                    SideRail(tab) { tab = it }
                    Box(Modifier.weight(1f).fillMaxHeight()) {
                        AnimatedContent(targetState = tab, label = "screen") { screen ->
                            when (screen) {
                                "HOME" -> HomeScreen(selectedLeague, { selectedLeague = it }) { selectedEvent = it }
                                "LIVE" -> LiveScreen { selectedEvent = it }
                                "SEARCH" -> SearchScreen { selectedEvent = it }
                                "SOURCES" -> SourcesScreen()
                                "SETTINGS" -> SettingsScreen()
                            }
                        }
                    }
                }
                selectedEvent?.let { event -> EventSheet(event, { selectedEvent = null }) { stream ->
                    selectedEvent = null
                    playingStream = stream
                } }
            }
        }
    }
}

@Composable
fun SideRail(tab: String, onTab: (String) -> Unit) {
    Column(
        modifier = Modifier.width(88.dp).fillMaxHeight().background(Color(0xFF0B0D12)).padding(vertical = 22.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        XtremeLogo(size = 58.dp)
        Spacer(Modifier.height(36.dp))
        listOf("🏠" to "HOME", "🔴" to "LIVE", "⌕" to "SEARCH", "▣" to "SOURCES", "⚙" to "SETTINGS").forEach { (icon, id) ->
            val active = tab == id
            Column(
                Modifier.padding(vertical = 7.dp)
                    .clip(RoundedCornerShape(18.dp))
                    .background(if (active) Color(0xFF25121A) else Color.Transparent)
                    .clickable { onTab(id) }
                    .padding(horizontal = 12.dp, vertical = 10.dp)
                    .semantics { testTag = "nav_${id.lowercase()}" },
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
    Row(Modifier.fillMaxWidth().padding(horizontal = 34.dp, vertical = 18.dp), verticalAlignment = Alignment.CenterVertically) {
        XtremeLogo(size = 54.dp)
        Spacer(Modifier.width(16.dp))
        Column(Modifier.weight(1f)) {
            Text(title, fontSize = 30.sp, fontWeight = FontWeight.Black, color = Color.White)
            subtitle?.let { Text(it, color = Color(0xFF858B98), fontSize = 13.sp) }
        }
        Box(Modifier.clip(RoundedCornerShape(22.dp)).background(Color(0xFF11151D)).padding(horizontal = 16.dp, vertical = 9.dp)) {
            Text("●  XTREME", color = Color(0xFFFF3D5A), fontWeight = FontWeight.Bold, fontSize = 11.sp)
        }
    }
}

@Composable
fun ScheduleLoader(
    modifier: Modifier = Modifier,
    content: @Composable (List<SportsEvent>) -> Unit
) {
    val state by ScheduleEngine.state.collectAsState()

    Box(modifier.fillMaxSize()) {
        when {
            state.loading && state.events.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = Color(0xFFFF1744))
            }
            state.error != null && state.events.isEmpty() -> Column(Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                Text("SCHEDULE UNAVAILABLE", color = Color(0xFFFF536C), fontWeight = FontWeight.Black)
                Spacer(Modifier.height(8.dp))
                Text(state.error!!, color = Color(0xFF858B98), fontSize = 12.sp)
            }
            else -> content(state.events)
        }
    }
}

@Composable
fun HomeScreen(selectedLeague: String, onLeague: (String) -> Unit, onEvent: (SportsEvent) -> Unit) {
    ScheduleLoader { events ->
        val filtered = events.filter { selectedLeague == "ALL" || SportsScheduleService.normalizeLeague(it.league) == SportsScheduleService.normalizeLeague(selectedLeague) }
        val featured = filtered.sortedWith(compareByDescending<SportsEvent> { it.isLive }.thenBy { it.startUtc }).take(10)
        val combat = filtered.filter { it.sport.contains("ufc", true) || it.league.contains("ufc", true) || it.league.contains("boxing", true) }.take(12)
        val all = filtered.take(18)

        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 40.dp)) {
            item {
                Header("SPORTS COMMAND CENTER", "Live events, upcoming fights and your connected TV sources")
                HeroBanner(featured.firstOrNull(), onEvent)
                LeagueChips(selectedLeague, onLeague)
            }
            item { SectionTitle(if (selectedLeague == "ALL") "FEATURED EVENTS" else selectedLeague) }
            item { EventRow(featured, onEvent) }
            if (combat.isNotEmpty()) {
                item { SectionTitle("COMBAT SPORTS") }
                item { EventRow(combat, onEvent) }
            }
            item { SectionTitle("ALL SPORTS") }
            item { EventRow(all, onEvent) }
        }
    }
}

@Composable
fun HeroBanner(event: SportsEvent?, onEvent: (SportsEvent) -> Unit) {
    Box(
        Modifier.padding(horizontal = 34.dp).fillMaxWidth().height(210.dp)
            .clip(RoundedCornerShape(28.dp))
            .clickable(enabled = event != null) { event?.let(onEvent) }
            .background(Brush.linearGradient(listOf(Color(0xFF260913), Color(0xFF121722), Color(0xFF321306))))
    ) {
        Column(Modifier.padding(28.dp).align(Alignment.CenterStart)) {
            Text(if (event?.isLive == true) "LIVE SPORTS" else "UP NEXT", color = Color(0xFFFF1744), fontWeight = FontWeight.Black, letterSpacing = 2.sp)
            Text(event?.title ?: "THE GAME IS ON.", color = Color.White, fontSize = 28.sp, fontWeight = FontWeight.Black, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Text(event?.let { formatEventTime(it.startUtc) } ?: "Canonical schedule loading…", color = Color(0xFFB6BBC5), fontSize = 14.sp)
            Spacer(Modifier.height(16.dp))
            Box(Modifier.clip(RoundedCornerShape(14.dp)).background(Color(0xFFFF1744)).padding(horizontal = 18.dp, vertical = 10.dp)) { Text("WATCH / FIND SOURCE →", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 12.sp) }
        }
        Text("⚡", Modifier.align(Alignment.CenterEnd).padding(end = 60.dp), fontSize = 92.sp)
    }
}

@Composable
fun LeagueChips(selected: String, onSelect: (String) -> Unit) {
    val leagues = listOf("ALL") + SportsScheduleService.uiLeagueChoices
    LazyRow(contentPadding = PaddingValues(horizontal = 34.dp, vertical = 22.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        items(leagues.distinct()) { league ->
            FilterChip(selected = selected == league, onClick = { onSelect(league) }, label = { Text(league, fontWeight = FontWeight.Bold) })
        }
    }
}

@Composable fun SectionTitle(text: String) { Text(text, Modifier.padding(start = 34.dp, top = 12.dp, bottom = 12.dp), color = Color.White, fontSize = 16.sp, fontWeight = FontWeight.Black, letterSpacing = 1.5.sp) }

@Composable
fun EventRow(events: List<SportsEvent>, onEvent: (SportsEvent) -> Unit) {
    if (events.isEmpty()) {
        Text("No events in this section.", Modifier.padding(horizontal = 34.dp, vertical = 18.dp), color = Color(0xFF737A87))
    } else {
        LazyRow(contentPadding = PaddingValues(horizontal = 34.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            items(events, key = { it.id }) { event -> EventCard(event, onEvent) }
        }
    }
}

@Composable
fun EventCard(event: SportsEvent, onEvent: (SportsEvent) -> Unit) {
    Column(Modifier.width(280.dp).clip(RoundedCornerShape(22.dp)).background(Color(0xFF11151D)).clickable { onEvent(event) }) {
        Box(Modifier.fillMaxWidth().height(140.dp).background(Brush.linearGradient(listOf(Color(0xFF242832), Color(0xFF0F1116)))), contentAlignment = Alignment.Center) {
            Row(horizontalArrangement = Arrangement.spacedBy(18.dp), verticalAlignment = Alignment.CenterVertically) {
                TeamLogo(event.homeLogo, event.home, 54.dp)
                Text("VS", color = Color(0xFF777F8C), fontSize = 11.sp, fontWeight = FontWeight.Black)
                TeamLogo(event.awayLogo, event.away, 54.dp)
            }
            Box(Modifier.align(Alignment.TopStart).padding(12.dp).clip(RoundedCornerShape(8.dp)).background(if (event.isLive) Color(0xFFFF1744) else Color(0xAA000000)).padding(horizontal = 8.dp, vertical = 5.dp)) {
                Text(if (event.isLive) "LIVE" else "UPCOMING", color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Black)
            }
        }
        Column(Modifier.padding(15.dp)) {
            Text(event.league, color = Color(0xFFFF536C), fontSize = 10.sp, fontWeight = FontWeight.Black, letterSpacing = 1.sp)
            Text(event.title, color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Bold, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Spacer(Modifier.height(7.dp))
            Text(formatEventTime(event.startUtc), color = Color(0xFF8D94A2), fontSize = 11.sp)
            if (event.broadcast.isNotBlank()) Text(event.broadcast, color = Color(0xFF6F7785), fontSize = 10.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
    }
}

@Composable
fun TeamLogo(url: String, name: String, size: androidx.compose.ui.unit.Dp) {
    if (url.isNotBlank()) {
        AsyncImage(model = url, contentDescription = name, modifier = Modifier.size(size))
    } else {
        Text(sportEmoji(name), fontSize = (size.value * .65f).sp)
    }
}

private fun sportEmoji(name: String): String = when {
    name.contains("ufc", true) || name.contains("boxing", true) || name.contains("fight", true) -> "🥊"
    name.contains("football", true) -> "🏈"
    name.contains("baseball", true) -> "⚾"
    name.contains("hockey", true) -> "🏒"
    name.contains("soccer", true) -> "⚽"
    else -> "🏆"
}

@Composable
fun LiveScreen(onEvent: (SportsEvent) -> Unit) {
    val state by ScheduleEngine.state.collectAsState()
    val live = state.liveEvents.sortedBy { it.startUtc }
    Column(Modifier.fillMaxSize()) {
        Header("LIVE NOW", "Real-time event state from the canonical sports schedule")
        when {
            state.loading && live.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = Color(0xFFFF1744))
            }
            state.error != null && live.isEmpty() -> EmptyState("Live feed unavailable")
            live.isEmpty() -> EmptyState("Nothing live right now")
            else -> LazyColumn(contentPadding = PaddingValues(34.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                items(live, key = { it.id }) { event -> LiveRow(event, onEvent) }
            }
        }
    }
}

@Composable
fun LiveRow(event: SportsEvent, onEvent: (SportsEvent) -> Unit) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Color(0xFF11151D)).clickable { onEvent(event) }.padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
        TeamLogo(event.homeLogo, event.home.ifBlank { event.title }, 42.dp)
        Spacer(Modifier.width(16.dp))
        Column(Modifier.weight(1f)) {
            Text(event.title, color = Color.White, fontWeight = FontWeight.Bold, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Text(event.league + " • LIVE", color = Color(0xFFFF536C), fontSize = 12.sp, fontWeight = FontWeight.Bold)
        }
        Text("WATCH →", color = Color(0xFFFF1744), fontWeight = FontWeight.Black, fontSize = 11.sp)
    }
}

@Composable
fun SearchScreen(onEvent: (SportsEvent) -> Unit) {
    var query by remember { mutableStateOf("") }
    var results by remember { mutableStateOf<List<EventSearchResult>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }

    LaunchedEffect(query) {
        delay(250)
        loading = true
        results = runCatching { EventFinder().search(query.trim(), 30) }.getOrDefault(emptyList())
        loading = false
    }

    Column(Modifier.fillMaxSize()) {
        Header("SEARCH SPORTS", "Search the same canonical schedule used by Home, Live and stream matching")
        OutlinedTextField(query, { query = it }, Modifier.fillMaxWidth().padding(horizontal = 34.dp), placeholder = { Text("Search Cowboys, UFC, boxing, NCAA…") }, singleLine = true)
        if (loading) LinearProgressIndicator(Modifier.fillMaxWidth().padding(horizontal = 34.dp), color = Color(0xFFFF1744))
        if (!loading && results.isEmpty()) EmptyState(if (query.isBlank()) "No scheduled events" else "No matching events")
        else LazyColumn(contentPadding = PaddingValues(34.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            items(results, key = { it.event.id }) { result ->
                LiveRow(result.event, onEvent)
            }
        }
    }
}

@Composable
fun SourcesScreen() {
    val context = androidx.compose.ui.platform.LocalContext.current
    val store = remember(context) { SourceStore(context) }
    var host by remember { mutableStateOf("") }
    var user by remember { mutableStateOf("") }
    var pass by remember { mutableStateOf("") }
    var saved by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(store) {
        val config = store.load()
        host = config.server
        user = config.username
        pass = config.password
        saved = config.isConfigured()
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize().imePadding(),
        contentPadding = PaddingValues(start = 34.dp, end = 34.dp, top = 4.dp, bottom = 36.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item { Header("SOURCE CENTER", "Connect your authorized Xtream Codes or M3U source") }
        item {
            Column(
                modifier = Modifier.widthIn(max = 720.dp).fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text("XTREAM CODES", color = Color(0xFFFF536C), fontWeight = FontWeight.Black, letterSpacing = 1.5.sp)
                OutlinedTextField(value = host, onValueChange = { host = it; saved = false; error = null }, modifier = Modifier.fillMaxWidth().semantics { testTag = "source_server" }, label = { Text("Server URL") }, placeholder = { Text("https://provider.example") }, singleLine = true)
                OutlinedTextField(value = user, onValueChange = { user = it; saved = false; error = null }, modifier = Modifier.fillMaxWidth().semantics { testTag = "source_username" }, label = { Text("Username") }, singleLine = true)
                OutlinedTextField(value = pass, onValueChange = { pass = it; saved = false; error = null }, modifier = Modifier.fillMaxWidth().semantics { testTag = "source_password" }, label = { Text("Password") }, singleLine = true)
                Button(onClick = { error = null; runCatching { store.save(SourceConfig(type = "XTREAM", server = host, username = user, password = pass)) }.onSuccess { saved = true }.onFailure { saved = false; error = it.message ?: "Could not save source" } }, modifier = Modifier.fillMaxWidth().height(52.dp).semantics { testTag = "source_connect" }, shape = RoundedCornerShape(14.dp)) { Text(if (saved) "SOURCE CONNECTED ✓" else "CONNECT SOURCE", fontWeight = FontWeight.Black) }
                if (saved) {
                    OutlinedButton(onClick = { store.clear(); host = ""; user = ""; pass = ""; saved = false; error = null }, modifier = Modifier.fillMaxWidth().height(48.dp).semantics { testTag = "source_disconnect" }, shape = RoundedCornerShape(14.dp)) { Text("DISCONNECT / LOG OUT", fontWeight = FontWeight.Black) }
                }
                error?.let { Text(it, color = Color(0xFFFF536C), fontSize = 12.sp) }
                Text("Credentials are kept on-device in the production build. Stream discovery only uses the source you connect.", color = Color(0xFF737A87), fontSize = 12.sp)
            }
        }
    }
}

@Composable
fun SettingsScreen() {
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 40.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        item { Header("SETTINGS", "Make XSportsX yours") }
        item { PairingQrCard(Modifier.padding(horizontal = 34.dp, vertical = 8.dp)) }
        item { SettingRow("Auto refresh", "Keep schedules and source matches current", true) }
        item { SettingRow("Live alerts", "Notify when a selected event is available", true) }
        item { SettingRow("TV mode", "Optimize controls and focus for Android TV", true) }
        item { SettingRow("Theme", "Obsidian / Red", false) }
    }
}

@Composable fun SettingRow(title: String, subtitle: String, checked: Boolean) { Row(Modifier.fillMaxWidth().padding(horizontal = 34.dp, vertical = 8.dp).clip(RoundedCornerShape(18.dp)).background(Color(0xFF11151D)).padding(18.dp), verticalAlignment = Alignment.CenterVertically) { Column(Modifier.weight(1f)) { Text(title, color = Color.White, fontWeight = FontWeight.Bold); Text(subtitle, color = Color(0xFF7D8491), fontSize = 12.sp) }; Switch(checked, {}) } }

@Composable fun EmptyState(text: String) { Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Column(horizontalAlignment = Alignment.CenterHorizontally) { Text("◉", fontSize = 48.sp, color = Color(0xFF333944)); Text(text, color = Color(0xFF858B98), fontSize = 16.sp, fontWeight = FontWeight.Bold) } } }

@Composable
fun EventSheet(event: SportsEvent, onClose: () -> Unit, onBack: () -> Unit = onClose, onPlay: (ResolvedStream) -> Unit) {
    val context = androidx.compose.ui.platform.LocalContext.current
    var loading by remember { mutableStateOf(true) }
    var streams by remember { mutableStateOf<List<ResolvedStream>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(event.id) {
        loading = true
        error = null
        runCatching { StreamResolver(context).loadMatchingEventStreams(event) }
            .onSuccess { streams = it }
            .onFailure { error = it.message ?: "Unable to resolve sources" }
        loading = false
    }

    Box(Modifier.fillMaxSize().background(Color(0x99000000)), contentAlignment = Alignment.BottomCenter) {
        Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(topStart = 30.dp, topEnd = 30.dp)).background(Color(0xFF10131A)).padding(28.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                TeamLogo(event.homeLogo, event.home.ifBlank { event.title }, 48.dp)
                Spacer(Modifier.width(16.dp))
                Column(Modifier.weight(1f)) {
                    Text(event.title, color = Color.White, fontSize = 21.sp, fontWeight = FontWeight.Black, maxLines = 2, overflow = TextOverflow.Ellipsis)
                    Text(event.league + " • " + formatEventTime(event.startUtc), color = Color(0xFF8A919E))
                }
                TextButton(onClick = onClose) { Text("CLOSE") }
            }
            Spacer(Modifier.height(20.dp))
            Text("SOURCE MATCHING", color = Color(0xFFFF536C), fontWeight = FontWeight.Black, letterSpacing = 1.2.sp)
            Text("Exact event matching uses the canonical schedule first, then your authorized Xtream/M3U source and approved public/official fallbacks.", color = Color(0xFF9AA1AE), fontSize = 13.sp)
            Spacer(Modifier.height(16.dp))
            when {
                loading -> Box(Modifier.fillMaxWidth().height(120.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator(color = Color(0xFFFF1744)) }
                error != null -> Text(error!!, color = Color(0xFFFF536C), fontSize = 12.sp)
                streams.isEmpty() -> EmptyState("No matching sources found")
                else -> {
                    Text("${streams.size} MATCHED SOURCES", color = Color(0xFF858B98), fontSize = 10.sp, fontWeight = FontWeight.Black)
                    Spacer(Modifier.height(8.dp))
                    streams.take(12).forEach { stream ->
                        Row(Modifier.fillMaxWidth().padding(vertical = 4.dp).clip(RoundedCornerShape(12.dp)).background(Color(0xFF171B24)).clickable { onPlay(stream) }.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text(stream.name, color = Color.White, fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                Text(stream.group, color = Color(0xFF777F8C), fontSize = 9.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            }
                            Text("PLAY →", color = Color(0xFF5CFF9D), fontSize = 9.sp, fontWeight = FontWeight.Black)
                        }
                    }
                }
            }
        }
    }
}

private fun formatEventTime(value: String): String = runCatching {
    DateTimeFormatter.ofPattern("EEE • h:mm a")
        .withZone(ZoneId.systemDefault())
        .format(Instant.parse(value))
}.getOrElse { value.ifBlank { "Time TBD" } }
