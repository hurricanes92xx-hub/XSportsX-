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
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil3.compose.AsyncImage
import kotlinx.coroutines.delay
import java.time.Instant
import java.time.ZoneId
import java.time.temporal.ChronoUnit
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/** League schedule UI backed only by the shared canonical schedule snapshot. */
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
        while (true) { now = Instant.now(); delay(30_000L) }
    }

    LaunchedEffect(canonicalLeague, reloadToken) {
        loading = true; error = null
        runCatching { ScheduleSnapshotRepository.all(reloadToken > 0).filter { it.league.let { value -> SportsScheduleService.scheduleLeaguesFor(canonicalLeague).contains(SportsScheduleService.canonicalLeagueFor(value)) } } }
            .onSuccess { loaded -> allEvents = loaded }
            .onFailure { error = it.message ?: "Schedule temporarily unavailable" }
        loading = false
    }

    if (streamFilter != null) {
        LiveChannelsScreen(filter = streamFilter, onBack = { streamFilter = null }); return
    }

    val zone = ZoneId.systemDefault()
    val today = now.atZone(zone).toLocalDate()
    val threeDayCutoff = now.plus(3, ChronoUnit.DAYS)
    val transitionGrace = now.minus(10, ChronoUnit.MINUTES)
    val visible = allEvents.filter { event ->
        val start = runCatching { Instant.parse(event.startUtc) }.getOrNull() ?: return@filter false
        if (tab == "LIVE") event.isLive else {
            val dateOnly = event.startUtc.matches(Regex(".*T00:00:00(?:\\.000)?Z$"))
            val localDate = start.atZone(zone).toLocalDate()
            val dateOnlyInWindow = dateOnly && !localDate.isBefore(today) && localDate.isBefore(today.plusDays(3))
            !event.isLive && (dateOnlyInWindow || (!start.isBefore(transitionGrace) && start.isBefore(threeDayCutoff)))
        }
    }.sortedBy { it.startUtc }
    val grouped = visible.groupBy { dayLabel(it.startUtc) }

    Column(Modifier.fillMaxSize().background(Color(0xFF05060A)).navigationBarsPadding()) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 16.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("‹", color = Color.White, fontSize = 36.sp, modifier = Modifier.clickable { onBack() })
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(canonicalLeague, color = Color.White, fontSize = 26.sp, fontWeight = FontWeight.Black, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(if (canonicalLeague == "WRESTLING") "WWE • AEW • TNA • AAA • NEXT 3 DAYS" else "${canonicalLeague} GAMES • NEXT 3 DAYS", color = Color(0xFF737B89), fontSize = 10.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            TextButton(onClick = { reloadToken++ }, enabled = !loading, contentPadding = PaddingValues(horizontal = 8.dp)) { Text(if (loading) "LOAD" else "REFRESH") }
        }
        Row(Modifier.padding(horizontal = 20.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(selected = tab == "LIVE", onClick = { tab = "LIVE" }, label = { Text("LIVE") })
            FilterChip(selected = tab == "UPCOMING", onClick = { tab = "UPCOMING" }, label = { Text("UPCOMING") })
        }
        Spacer(Modifier.height(8.dp))
        when {
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator(color = Color(0xFFFF1744)) }
            error != null && visible.isEmpty() -> Box(Modifier.fillMaxSize().padding(28.dp), contentAlignment = Alignment.Center) { Text(error!!, color = Color.White) }
            visible.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text(if (tab == "LIVE") "No live ${canonicalLeague} games right now" else "No upcoming ${canonicalLeague} events in the next 3 days", color = Color(0xFF858B98), textAlign = androidx.compose.ui.text.style.TextAlign.Center) }
            else -> LazyColumn(contentPadding = PaddingValues(horizontal = 20.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
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
    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Color(0xFF10141C)).padding(12.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(56.dp).clip(RoundedCornerShape(12.dp)).background(Color(0xFF080B11)), contentAlignment = Alignment.Center) {
                if (event.artUrl.isNotBlank()) AsyncImage(model = event.artUrl, contentDescription = event.league, modifier = Modifier.fillMaxSize().padding(9.dp), contentScale = ContentScale.Fit)
                else XSportsLeagueLogo(event.league, size = 42.dp)
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                if (event.away.isNotBlank() && event.home.isNotBlank()) {
                    TeamLine(event.away, event.awayLogo, "AWAY")
                    TeamLine(event.home, event.homeLogo, "HOME")
                } else Text(event.title.ifBlank { event.league }, color = Color.White, fontWeight = FontWeight.Black, maxLines = 2, overflow = TextOverflow.Ellipsis)
            }
        }
        Spacer(Modifier.height(10.dp))
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(if (event.isLive) "LIVE • ${event.status.ifBlank { event.state }}" else formatTime(event.startUtc), color = if (event.isLive) Color(0xFFFF536C) else Color(0xFF7F8795), fontSize = 10.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                if (event.broadcast.isNotBlank()) Text(event.broadcast, color = Color(0xFF9BA4B2), fontSize = 9.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            if (event.isLive) Button(onClick = onWatch, colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFF1744)), contentPadding = PaddingValues(horizontal = 14.dp, vertical = 0.dp)) { Text("WATCH", fontSize = 10.sp, fontWeight = FontWeight.Black) }
            else Surface(color = Color(0xFF171C26), shape = RoundedCornerShape(8.dp)) { Text("UPCOMING", color = Color(0xFF9BA4B2), fontSize = 8.sp, fontWeight = FontWeight.Black, modifier = Modifier.padding(horizontal = 8.dp, vertical = 5.dp)) }
        }
    }
}

@Composable
private fun TeamLine(name: String, logo: String, label: String) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
        Box(Modifier.size(30.dp), contentAlignment = Alignment.Center) {
            if (logo.isNotBlank()) AsyncImage(model = logo, contentDescription = name, modifier = Modifier.size(28.dp), contentScale = ContentScale.Fit)
            else XSportsLeagueLogo(name, size = 26.dp)
        }
        Spacer(Modifier.width(7.dp))
        Text(name, color = Color.White, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
        Spacer(Modifier.width(8.dp))
        Text(label, color = Color(0xFF667080), fontSize = 8.sp, fontWeight = FontWeight.Black, modifier = Modifier.width(42.dp), maxLines = 1)
    }
}

private fun dayLabel(startUtc: String): String = runCatching { SimpleDateFormat("EEE, MMM d", Locale.US).apply { timeZone = TimeZone.getDefault() }.format(Date.from(Instant.parse(startUtc))) }.getOrElse { "SCHEDULE" }
private fun formatTime(startUtc: String): String = runCatching { SimpleDateFormat("EEE • h:mm a", Locale.US).apply { timeZone = TimeZone.getDefault() }.format(Date.from(Instant.parse(startUtc))) }.getOrElse { startUtc }
