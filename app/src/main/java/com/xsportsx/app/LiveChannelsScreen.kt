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
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull

@Composable
fun LiveChannelsScreen(filter: String? = null, event: SportsEvent? = null, onBack: () -> Unit) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val scope = rememberCoroutineScope()
    val healthStore = remember { StreamHealthStore(context) }
    val playbackHealth = remember { PlaybackHealthStore(context) }
    val fastXtream = remember { FastXtreamEventResolver(context) }
    val fastPublic = remember { FastPublicSourceSelector(context) }
    val engineState by ScheduleEngine.state.collectAsState()
    var streams by remember { mutableStateOf<List<ResolvedStream>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var refreshing by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var playerStream by remember { mutableStateOf<ResolvedStream?>(null) }
    var selectedEvent by remember { mutableStateOf<SportsEvent?>(event) }
    var favorites by remember { mutableStateOf(ChannelFavorites.load(context)) }
    var showFavorites by remember { mutableStateOf(false) }
    var reloadJob by remember { mutableStateOf<kotlinx.coroutines.Job?>(null) }
    val liveEvents = engineState.liveEvents
    val playbackEventKey = selectedEvent?.let { EventIdentity.id(it) }.orEmpty()

    fun ranked(list: List<ResolvedStream>): List<ResolvedStream> = list.distinctBy { it.url }
        .sortedWith(compareByDescending<ResolvedStream> { stream -> healthStore.score(stream.url) + playbackHealth.score(playbackEventKey, stream) + playbackHealth.globalScore(stream) }.thenBy { it.name.lowercase() })

    fun reload(force: Boolean = false, background: Boolean = false) {
        reloadJob?.cancel()
        val requestEventId = selectedEvent?.let { EventIdentity.id(it) }.orEmpty()
        val requestFilter = filter
        reloadJob = scope.launch {
            if (background) refreshing = true else loading = true
            if (!background) error = null
            val result = runCatching {
                ScheduleEngine.start(context)
                when {
                    selectedEvent != null -> {
                        val target = selectedEvent!!
                        val fast = withTimeoutOrNull(2_800L) { fastXtream.resolve(target) }.orEmpty()
                        if (fast.isNotEmpty()) return@runCatching fast
                        val config = SourceStore(context).load()
                        val authorized = when {
                            config.type == "XTREAM" && config.isConfigured() -> listOf(AuthorizedSource("user-xtream", AuthorizedSource.Type.XTREAM, config.server, config.username, config.password))
                            config.type == "M3U" && config.isConfigured() -> listOf(AuthorizedSource("user-m3u", AuthorizedSource.Type.M3U, config.m3uUrl))
                            else -> emptyList()
                        }
                        val targeted = withTimeoutOrNull(2_200L) { fastPublic.candidates(target, authorized, 8) }.orEmpty()
                            .map { ResolvedStream("${it.name} • ${it.sourceId}", it.group, it.url) }
                        if (targeted.isNotEmpty()) return@runCatching targeted
                        withTimeoutOrNull(1_500L) { StreamResolver(context).loadMatchingEventStreams(target, force) }.orEmpty()
                    }
                    !requestFilter.isNullOrBlank() -> withTimeoutOrNull(8_000L) { StreamResolver(context).loadMatchingStreams(requestFilter, force) }.orEmpty()
                    else -> {
                        if (force || ScheduleEngine.state.value.events.isEmpty()) ScheduleEngine.refreshNow()
                        emptyList<ResolvedStream>()
                    }
                }
            }
            if (selectedEvent?.let { EventIdentity.id(it) }.orEmpty() != requestEventId) return@launch
            result.onSuccess { resolved ->
                if (selectedEvent != null || !requestFilter.isNullOrBlank()) streams = ranked(resolved)
                error = null
            }.onFailure { if (!background) error = it.message ?: "Unable to load live events" }
            if (background) refreshing = false else loading = false
        }
    }

    LaunchedEffect(filter, selectedEvent?.id) {
        streams = emptyList(); playerStream = null; loading = true; error = null; reload(false)
    }

    if (playerStream != null) {
        val activeStream = playerStream!!
        NativePlayerScreen(activeStream.url, activeStream.name, eventId = selectedEvent?.let { EventIdentity.id(it) }.orEmpty(), onBack = { playerStream = null }, onPlaybackSuccess = { healthStore.recordSuccess(activeStream.url); streams = ranked(streams) }, onPlaybackFailure = {
            healthStore.recordFailure(activeStream.url); streams = ranked(streams)
            val next = streams.firstOrNull { it.url != activeStream.url }
            if (next != null) playerStream = next else if (selectedEvent != null) scope.launch {
                val requestedId = EventIdentity.id(selectedEvent!!)
                val refreshed = runCatching { StreamResolver(context).loadMatchingEventStreams(selectedEvent!!, true) }.getOrDefault(emptyList())
                if (EventIdentity.id(selectedEvent ?: return@launch) != requestedId) return@launch
                streams = ranked(refreshed); playerStream = streams.firstOrNull { it.url != activeStream.url }
            } else playerStream = null
        })
        return
    }

    val visibleStreams = remember(streams, favorites, showFavorites) { if (showFavorites) streams.filter { ChannelFavorites.isFavorite(context, it) } else streams }
    Column(Modifier.fillMaxSize().background(Color(0xFF05060A)).statusBarsPadding().navigationBarsPadding()) {
        Row(Modifier.fillMaxWidth().padding(22.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("‹", color = Color.White, fontSize = 36.sp, modifier = Modifier.clickable { if (selectedEvent != null && event == null) selectedEvent = null else onBack() })
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(when { selectedEvent != null -> "GAME STREAMS"; filter.isNullOrBlank() -> "LIVE GAMES"; else -> "GAME STREAMS" }, color = Color.White, fontSize = 24.sp, fontWeight = FontWeight.Black)
                Text(when { selectedEvent != null -> "${selectedEvent!!.title.ifBlank { "Live event" }} • ${selectedEvent!!.league} • ${streams.size} sources"; filter.isNullOrBlank() -> "Live events across all leagues • ${liveEvents.size} games"; showFavorites -> "MY FAVORITES • ${visibleStreams.size} channels"; else -> "Free public + authorized streams • ${streams.size} matches" }, color = Color(0xFF737B89), fontSize = 11.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
            }
            if (selectedEvent == null && !filter.isNullOrBlank()) TextButton(onClick = { showFavorites = !showFavorites; favorites = ChannelFavorites.load(context) }) { Text(if (showFavorites) "ALL" else "★ ${favorites.size}", color = if (showFavorites) Color.White else Color(0xFFFF1744)) }
            TextButton(onClick = { reload(true, background = true) }) { Text("REFRESH") }
        }
        if (refreshing || engineState.refreshing) LinearProgressIndicator(Modifier.fillMaxWidth(), color = Color(0xFFFF1744))
        when {
            loading && liveEvents.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator(color = Color(0xFFFF1744)) }
            error != null && (selectedEvent != null || streams.isEmpty() && liveEvents.isEmpty()) -> Box(Modifier.fillMaxSize().padding(30.dp), contentAlignment = Alignment.Center) { Column(horizontalAlignment = Alignment.CenterHorizontally) { Text("STREAM ERROR", color = Color(0xFFFF536C), fontWeight = FontWeight.Black); Spacer(Modifier.height(8.dp)); Text(error!!, color = Color.White); Spacer(Modifier.height(12.dp)); TextButton(onClick = { reload(true) }) { Text("RETRY") } } }
            selectedEvent == null && filter.isNullOrBlank() && liveEvents.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("No live games right now", color = Color(0xFF858B98)) }
            selectedEvent == null && filter.isNullOrBlank() -> LazyColumn(contentPadding = PaddingValues(horizontal = 22.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) { items(liveEvents, key = { EventIdentity.id(it) }) { game -> Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Color(0xFF10141C)).clickable { streams = emptyList(); loading = true; error = null; selectedEvent = game }.padding(16.dp), verticalAlignment = Alignment.CenterVertically) { Box(Modifier.size(48.dp).background(Color(0xFF1A202B), RoundedCornerShape(12.dp)), contentAlignment = Alignment.Center) { Text("LIVE", color = Color(0xFFFF1744), fontSize = 9.sp, fontWeight = FontWeight.Black) }; Spacer(Modifier.width(14.dp)); Column(Modifier.weight(1f)) { Text(game.league, color = Color(0xFFFF1744), fontSize = 10.sp, fontWeight = FontWeight.Black); Text("${game.away} @ ${game.home}", color = Color.White, fontWeight = FontWeight.Bold, maxLines = 2, overflow = TextOverflow.Ellipsis); Text(if (game.isLive) "LIVE" else "UPCOMING", color = Color(0xFF777F8C), fontSize = 10.sp) }; Text("WATCH", color = Color(0xFFFF1744), fontSize = 10.sp, fontWeight = FontWeight.Black) } } }
            streams.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { if (loading) CircularProgressIndicator(color = Color(0xFFFF1744)) else Text("No matching public or authorized game streams found", color = Color(0xFF858B98)) }
            showFavorites && visibleStreams.isEmpty() -> Box(Modifier.fillMaxSize().padding(30.dp), contentAlignment = Alignment.Center) { Column(horizontalAlignment = Alignment.CenterHorizontally) { Text("★", color = Color(0xFFFF1744), fontSize = 42.sp); Spacer(Modifier.height(8.dp)); Text("NO FAVORITE CHANNELS YET", color = Color.White, fontWeight = FontWeight.Black); Spacer(Modifier.height(6.dp)); Text("Tap the star on any channel to save it here.", color = Color(0xFF858B98), fontSize = 12.sp) } }
            else -> LazyColumn(contentPadding = PaddingValues(horizontal = 22.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) { items(visibleStreams, key = { it.url }) { stream -> val favorite = ChannelFavorites.isFavorite(context, stream); Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Color(0xFF10141C)).padding(16.dp), verticalAlignment = Alignment.CenterVertically) { Box(Modifier.size(44.dp).background(Color(0xFF1A202B), RoundedCornerShape(12.dp)).clickable { playerStream = stream }, contentAlignment = Alignment.Center) { Text("▶", color = Color(0xFFFF1744), fontWeight = FontWeight.Black) }; Spacer(Modifier.width(14.dp)); Column(Modifier.weight(1f).clickable { playerStream = stream }) { Text(stream.name, color = Color.White, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis); Text(stream.group, color = Color(0xFF777F8C), fontSize = 10.sp, maxLines = 1, overflow = TextOverflow.Ellipsis) }; TextButton(onClick = { ChannelFavorites.toggle(context, stream); favorites = ChannelFavorites.load(context) }) { Text(if (favorite) "★" else "☆", color = if (favorite) Color(0xFFFF1744) else Color(0xFF737B89), fontSize = 22.sp) }; Text("WATCH", color = Color(0xFFFF1744), fontSize = 10.sp, fontWeight = FontWeight.Black, modifier = Modifier.clickable { playerStream = stream }) } } }
        }
    }
}
