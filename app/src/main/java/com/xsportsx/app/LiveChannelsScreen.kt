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
import kotlinx.coroutines.launch

@Composable
fun LiveChannelsScreen(filter: String? = null, event: SportsEvent? = null, onBack: () -> Unit) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val scope = rememberCoroutineScope()
    var streams by remember { mutableStateOf<List<ResolvedStream>>(emptyList()) }
    var liveEvents by remember { mutableStateOf<List<SportsEvent>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var playerStream by remember { mutableStateOf<ResolvedStream?>(null) }
    var selectedEvent by remember { mutableStateOf<SportsEvent?>(event) }

    fun reload(force: Boolean = false) {
        scope.launch {
            loading = true
            error = null
            runCatching {
                if (selectedEvent != null) {
                    val resolver = StreamResolver(context)
                    resolver.loadMatchingEventStreams(selectedEvent!!, force)
                } else if (filter.isNullOrBlank()) {
                    // Live Center is event-first. Never load the entire public IPTV catalog here.
                    SportsScheduleService.load()
                        .filter { it.isLive }
                        .distinctBy { it.id.ifBlank { "${it.league}|${it.home}|${it.away}|${it.startUtc}" } }
                        .sortedWith(compareBy<SportsEvent> { it.league.lowercase() }.thenBy { it.startUtc })
                } else {
                    val resolver = StreamResolver(context)
                    resolver.loadMatchingStreams(filter, force)
                }
            }
                .onSuccess { result ->
                    if (selectedEvent != null || !filter.isNullOrBlank()) {
                        @Suppress("UNCHECKED_CAST")
                        streams = result as List<ResolvedStream>
                    } else {
                        @Suppress("UNCHECKED_CAST")
                        liveEvents = result as List<SportsEvent>
                    }
                }
                .onFailure { error = it.message ?: "Unable to load live events" }
            loading = false
        }
    }

    LaunchedEffect(filter, selectedEvent?.id) { reload(false) }

    if (playerStream != null) {
        NativePlayerScreen(playerStream!!.url, playerStream!!.name) { playerStream = null }
        return
    }

    Column(Modifier.fillMaxSize().background(Color(0xFF05060A))) {
        Row(Modifier.fillMaxWidth().padding(22.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("‹", color = Color.White, fontSize = 36.sp, modifier = Modifier.clickable {
                if (selectedEvent != null && event == null) selectedEvent = null else onBack()
            })
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    when {
                        selectedEvent != null -> "GAME STREAMS"
                        filter.isNullOrBlank() -> "LIVE GAMES"
                        else -> "GAME STREAMS"
                    },
                    color = Color.White, fontSize = 24.sp, fontWeight = FontWeight.Black
                )
                Text(
                    when {
                        selectedEvent != null -> "${selectedEvent!!.title.ifBlank { "Live event" }} • ${selectedEvent!!.league} • ${streams.size} sources"
                        filter.isNullOrBlank() -> "Live events across all leagues • ${liveEvents.size} games"
                        else -> "Free public + authorized streams • ${streams.size} matches"
                    },
                    color = Color(0xFF737B89), fontSize = 11.sp, maxLines = 2, overflow = TextOverflow.Ellipsis
                )
            }
            TextButton(onClick = { reload(true) }) { Text("REFRESH") }
        }

        when {
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = Color(0xFFFF1744))
            }
            error != null -> Box(Modifier.fillMaxSize().padding(30.dp), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("SCHEDULE ERROR", color = Color(0xFFFF536C), fontWeight = FontWeight.Black)
                    Spacer(Modifier.height(8.dp)); Text(error!!, color = Color.White)
                    Spacer(Modifier.height(12.dp)); TextButton(onClick = { reload(true) }) { Text("RETRY") }
                }
            }
            selectedEvent == null && filter.isNullOrBlank() && liveEvents.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("No live games right now", color = Color(0xFF858B98))
            }
            selectedEvent == null && filter.isNullOrBlank() -> LazyColumn(
                contentPadding = PaddingValues(horizontal = 22.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                items(liveEvents, key = { it.id.ifBlank { "${it.league}|${it.home}|${it.away}|${it.startUtc}" } }) { game ->
                    Row(
                        Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Color(0xFF10141C))
                            .clickable { selectedEvent = game }.padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Box(Modifier.size(48.dp).background(Color(0xFF1A202B), RoundedCornerShape(12.dp)), contentAlignment = Alignment.Center) {
                            Text("LIVE", color = Color(0xFFFF1744), fontSize = 9.sp, fontWeight = FontWeight.Black)
                        }
                        Spacer(Modifier.width(14.dp))
                        Column(Modifier.weight(1f)) {
                            Text(game.league, color = Color(0xFFFF1744), fontSize = 10.sp, fontWeight = FontWeight.Black)
                            Text("${game.away} @ ${game.home}", color = Color.White, fontWeight = FontWeight.Bold, maxLines = 2, overflow = TextOverflow.Ellipsis)
                            Text(game.status.ifBlank { "LIVE" }, color = Color(0xFF777F8C), fontSize = 10.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        }
                        Text("WATCH", color = Color(0xFFFF1744), fontSize = 10.sp, fontWeight = FontWeight.Black)
                    }
                }
            }
            streams.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("No matching public or authorized game streams found", color = Color(0xFF858B98))
            }
            else -> LazyColumn(contentPadding = PaddingValues(horizontal = 22.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                items(streams, key = { it.url }) { stream ->
                    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Color(0xFF10141C)).clickable { playerStream = stream }.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(44.dp).background(Color(0xFF1A202B), RoundedCornerShape(12.dp)), contentAlignment = Alignment.Center) { Text("▶", color = Color(0xFFFF1744), fontWeight = FontWeight.Black) }
                        Spacer(Modifier.width(14.dp))
                        Column(Modifier.weight(1f)) {
                            Text(stream.name, color = Color.White, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            Text(stream.group, color = Color(0xFF777F8C), fontSize = 10.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        }
                        Text("WATCH", color = Color(0xFFFF1744), fontSize = 10.sp, fontWeight = FontWeight.Black)
                    }
                }
            }
        }
    }
}
