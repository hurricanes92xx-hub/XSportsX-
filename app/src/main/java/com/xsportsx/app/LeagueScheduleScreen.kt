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
import kotlinx.coroutines.delay
import kotlinx.coroutines.withTimeoutOrNull
import java.time.Instant
import java.time.temporal.ChronoUnit
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/** League schedule UI with a bounded canonical-first scoreboard load. */
@Composable
fun LeagueScheduleScreen(league: String, onBack: () -> Unit) {
    val canonicalLeague = SportsScheduleService.canonicalLeagueFor(league)
    var allEvents by remember(canonicalLeague) { mutableStateOf<List<SportsEvent>>(emptyList()) }
    var loading by remember(canonicalLeague) { mutableStateOf(true) }
    var error by remember(canonicalLeague) { mutableStateOf<String?>(null) }
    var tab by remember(canonicalLeague) { mutableStateOf("UPCOMING") }
    var streamFilter by remember { mutableStateOf<String?>(null) }
    var reloadToken by remember(canonicalLeague) { mutableIntStateOf(0) }
    var now by remember(canonicalLeague) { mutableStateOf(Instant.now()) }

    LaunchedEffect(canonicalLeague) {
        while (true) {
            now = Instant.now()
            delay(30_000L)
        }
    }

    LaunchedEffect(canonicalLeague, reloadToken) {
        loading = true
        error = null
        val loaded = withTimeoutOrNull(11_000L) {
            val canonical = runCatching { CanonicalScheduleProvider.load(canonicalLeague, 3) }.getOrDefault(emptyList())
            if (canonical.isNotEmpty()) canonical
            else runCatching { SportsScheduleService.loadForLeague(canonicalLeague, 3) }.getOrDefault(emptyList())
        }.orEmpty()
        if (loaded.isNotEmpty()) {
            allEvents = loaded
        } else {
            val recovered = withTimeoutOrNull(5_000L) {
                runCatching { ReliableLeagueScheduleFallback.load(canonicalLeague, 3) }.getOrDefault(emptyList())
            }.orEmpty()
            if (recovered.isNotEmpty()) allEvents = recovered
            else if (allEvents.isEmpty()) error = "Schedule temporarily unavailable"
        }
        loading = false
    }

    if (streamFilter != null) {
        LiveChannelsScreen(filter = streamFilter, onBack = { streamFilter = null })
        return
    }

    val threeDayCutoff = now.plus(3, ChronoUnit.DAYS)
    val transitionGrace = now.minus(10, ChronoUnit.MINUTES)
    val visible = allEvents.filter { event ->
        val start = runCatching { Instant.parse(event.startUtc) }.getOrNull() ?: return@filter false
        if (tab == "LIVE") event.isLive
        else !event.isLive && !start.isBefore(transitionGrace) && start.isBefore(threeDayCutoff)
    }.sortedBy { it.startUtc }
    val grouped = visible.groupBy { dayLabel(it.startUtc) }

    Column(Modifier.fillMaxSize().background(Color(0xFF05060A))) {
        Row(Modifier.fillMaxWidth().padding(20.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("‹", color = Color.White, fontSize = 36.sp, modifier = Modifier.clickable { onBack() })
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(canonicalLeague, color = Color.White, fontSize = 27.sp, fontWeight = FontWeight.Black)
                Text("${canonicalLeague} GAMES • NEXT 3 DAYS", color = Color(0xFF737B89), fontSize = 10.sp, fontWeight = FontWeight.Bold)
            }
            TextButton(onClick = { reloadToken++ }, enabled = !loading) { Text(if (loading) "LOADING" else "REFRESH") }
        }
        Row(Modifier.padding(horizontal = 20.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(selected = tab == "LIVE", onClick = { tab = "LIVE" }, label = { Text("LIVE") })
            FilterChip(selected = tab == "UPCOMING", onClick = { tab = "UPCOMING" }, label = { Text("UPCOMING") })
        }
        Spacer(Modifier.height(8.dp))
        when {
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator(color = Color(0xFFFF1744)) }
            error != null && visible.isEmpty() -> Box(Modifier.fillMaxSize().padding(28.dp), contentAlignment = Alignment.Center) { Text(error!!, color = Color.White) }
            visible.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(if (tab == "LIVE") "No live ${canonicalLeague} games right now" else "No upcoming ${canonicalLeague} games in the next 3 days", color = Color(0xFF858B98))
            }
            else -> LazyColumn(contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                grouped.forEach { (day, events) ->
                    item { Text(day, color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Black, modifier = Modifier.padding(top = 8.dp)) }
                    items(events, key = { it.id.ifBlank { "${it.league}|${it.away}|${it.home}|${it.startUtc}" } }) { event ->
                        LeagueEventCard(event) { streamFilter = "${event.league} ${event.away} ${event.home}" }
                    }
                }
            }
        }
    }
}

@Composable
private fun LeagueEventCard(event: SportsEvent, onWatch: () -> Unit) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Color(0xFF10141C)).padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(event.away.ifBlank { "TBD" }, color = Color.White, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text("@ ${event.home.ifBlank { "TBD" }}", color = Color(0xFFB6BDCA), fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Spacer(Modifier.height(5.dp))
            Text(if (event.isLive) "LIVE • ${event.status.ifBlank { event.state }}" else formatTime(event.startUtc), color = if (event.isLive) Color(0xFFFF536C) else Color(0xFF7F8795), fontSize = 10.sp)
            if (event.broadcast.isNotBlank()) Text(event.broadcast, color = Color(0xFF9BA4B2), fontSize = 9.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        if (event.isLive) Button(onClick = onWatch, colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFF1744))) { Text("WATCH") }
        else Text("UPCOMING", color = Color(0xFF9BA4B2), fontSize = 9.sp, fontWeight = FontWeight.Black)
    }
}

private fun dayLabel(startUtc: String): String = runCatching {
    SimpleDateFormat("EEE, MMM d", Locale.US).apply { timeZone = TimeZone.getDefault() }.format(Date.from(Instant.parse(startUtc)))
}.getOrElse { "SCHEDULE" }

private fun formatTime(startUtc: String): String = runCatching {
    SimpleDateFormat("EEE • h:mm a", Locale.US).apply { timeZone = TimeZone.getDefault() }.format(Date.from(Instant.parse(startUtc)))
}.getOrElse { startUtc }