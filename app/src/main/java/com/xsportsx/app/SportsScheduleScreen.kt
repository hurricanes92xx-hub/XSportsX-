package com.xsportsx.app

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil3.compose.AsyncImage
import kotlinx.coroutines.launch
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

@Composable
fun SportsScheduleScreen(onBack: () -> Unit, onEvent: (SportsEvent) -> Unit) {
    val scope = rememberCoroutineScope()
    var events by remember { mutableStateOf<List<SportsEvent>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var filter by remember { mutableStateOf("ALL") }

    fun refresh() {
        scope.launch {
            loading = true
            error = null
            runCatching { SportsScheduleService.load() }
                .onSuccess { events = it }
                .onFailure { error = it.message ?: "Unable to load schedules" }
            loading = false
        }
    }

    LaunchedEffect(Unit) { refresh() }

    val visible = when (filter) {
        "LIVE" -> events.filter { it.isLive }
        "UPCOMING" -> events.filter { it.isUpcoming }
        else -> events
    }

    Column(Modifier.fillMaxSize().background(Color(0xFF07080C))) {
        Row(Modifier.fillMaxWidth().padding(28.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("‹", color = Color.White, fontSize = 38.sp, modifier = Modifier.clickable { onBack() })
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text("LIVE + UPCOMING", color = Color.White, fontSize = 28.sp, fontWeight = FontWeight.Black)
                Text("Sports schedule", color = Color(0xFF858B98), fontSize = 12.sp)
            }
            TextButton(onClick = { refresh() }) { Text("REFRESH") }
        }
        Row(Modifier.padding(horizontal = 28.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("ALL", "LIVE", "UPCOMING").forEach { value -> FilterChip(selected = filter == value, onClick = { filter = value }, label = { Text(value) }) }
        }
        when {
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator(color = Color(0xFFFF1744)) }
            error != null -> Box(Modifier.fillMaxSize().padding(30.dp), contentAlignment = Alignment.Center) { Column(horizontalAlignment = Alignment.CenterHorizontally) { Text("SCHEDULE ERROR", color = Color(0xFFFF536C), fontWeight = FontWeight.Black); Spacer(Modifier.height(8.dp)); Text(error!!, color = Color.White); Spacer(Modifier.height(12.dp)); TextButton(onClick = { refresh() }) { Text("TRY AGAIN") } } }
            visible.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text(if (filter == "LIVE") "Nothing live right now" else "No events found", color = Color(0xFF858B98)) }
            else -> LazyColumn(contentPadding = PaddingValues(28.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) { items(visible, key = { it.id }) { event -> ScheduleEventCard(event) { onEvent(event) } } }
        }
    }
}

@Composable
private fun ScheduleEventCard(event: SportsEvent, onClick: () -> Unit) {
    val combat = event.league.equals("UFC", true) || event.league.equals("BOXING", true) || event.sport.equals("MMA", true)
    val racing = event.league.equals("F1", true) || event.sport.equals("Racing", true)
    val art = event.artUrl.trim()
    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp)).background(Color(0xFF0E121A)).clickable { onClick() }) {
        Box(Modifier.fillMaxWidth().height(if (combat || racing) 185.dp else 170.dp).background(cardBrush(event, combat, racing))) {
            if (art.isNotBlank()) {
                AsyncImage(model = art, contentDescription = null, modifier = Modifier.fillMaxSize(), contentScale = ContentScale.Crop, alpha = 0.48f)
                Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color.Transparent, Color(0xCC080A10)))))
            }
            if (combat || racing) {
                Column(Modifier.align(Alignment.TopStart).padding(16.dp)) {
                    Text(when { event.league.equals("UFC", true) -> "UFC • FIGHT EVENT"; event.league.equals("BOXING", true) -> "BOXING • EVENT NIGHT"; else -> "F1 • GRAND PRIX" }, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black, letterSpacing = 1.4.sp)
                    Spacer(Modifier.height(5.dp)); Text(event.title.ifBlank { event.league }, color = Color.White, fontSize = 22.sp, fontWeight = FontWeight.Black)
                }
                EventArtBadge(event, combat, racing, Modifier.align(Alignment.Center))
            } else LogoVsLogo(event, Modifier.align(Alignment.Center))
            Surface(color = if (event.isLive) Color(0xFFFF1744) else Color(0xDD0A0D13), shape = RoundedCornerShape(9.dp), modifier = Modifier.align(Alignment.TopEnd).padding(14.dp)) {
                Text(if (event.isLive) "● LIVE" else event.league.uppercase(), color = Color.White, modifier = Modifier.padding(horizontal = 9.dp, vertical = 6.dp), fontSize = 9.sp, fontWeight = FontWeight.Black)
            }
        }
        Row(Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(if (event.isLive) "LIVE NOW" else formatTime(event.startUtc), color = if (event.isLive) Color(0xFFFF1744) else Color(0xFFB8BEC8), fontSize = 11.sp, fontWeight = FontWeight.Bold)
                Text(event.status.ifBlank { event.broadcast }.ifBlank { "EVENT" }, color = Color(0xFF7F8794), fontSize = 10.sp)
            }
            Text("VIEW CARD →", color = Color(0xFFFF1744), fontSize = 10.sp, fontWeight = FontWeight.Black)
        }
    }
}

@Composable
private fun LogoVsLogo(event: SportsEvent, modifier: Modifier = Modifier) {
    Row(modifier, verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.Center) {
        TeamLogo(event.homeLogo, event.home.ifBlank { "HOME" }, 66.dp)
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(horizontal = 18.dp)) {
            Text("VS", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Black, letterSpacing = 1.sp)
            Text(event.league.uppercase(), color = Color(0xFFFF536C), fontSize = 8.sp, fontWeight = FontWeight.Black)
        }
        TeamLogo(event.awayLogo, event.away.ifBlank { "AWAY" }, 66.dp)
    }
}

@Composable
private fun TeamLogo(url: String, name: String, size: androidx.compose.ui.unit.Dp) {
    Box(Modifier.size(size).clip(CircleShape).background(Brush.radialGradient(listOf(Color(0xFF202A38), Color(0xFF0C1017)))), contentAlignment = Alignment.Center) {
        // Keep a deterministic fallback visible underneath the network image. Coil's AsyncImage
        // otherwise leaves the dark placeholder when a provider logo URL is missing or fails.
        Text(teamInitials(name), color = Color.White, fontSize = 17.sp, fontWeight = FontWeight.Black)
        if (url.isNotBlank()) {
            AsyncImage(model = url, contentDescription = name, modifier = Modifier.fillMaxSize().padding(7.dp), contentScale = ContentScale.Fit)
        }
    }
}

@Composable
private fun EventArtBadge(event: SportsEvent, combat: Boolean, racing: Boolean, modifier: Modifier = Modifier) {
    Box(modifier.size(82.dp).clip(RoundedCornerShape(20.dp)).background(Color(0xB50A0D13)), contentAlignment = Alignment.Center) {
        Text(when { racing -> "F1"; combat && event.league.equals("UFC", true) -> "UFC"; else -> "BOX" }, color = Color.White, fontSize = 22.sp, fontWeight = FontWeight.Black, letterSpacing = 1.sp)
    }
}

private fun cardBrush(event: SportsEvent, combat: Boolean, racing: Boolean): Brush = when {
    racing -> Brush.linearGradient(listOf(Color(0xFF120B14), Color(0xFF111A2B), Color(0xFF29080E)))
    combat && event.league.equals("UFC", true) -> Brush.linearGradient(listOf(Color(0xFF28070D), Color(0xFF10141C), Color(0xFF3A1010)))
    combat -> Brush.linearGradient(listOf(Color(0xFF29100A), Color(0xFF15141A), Color(0xFF3A0A18)))
    else -> Brush.linearGradient(listOf(Color(0xFF250812), Color(0xFF111722), Color(0xFF211108)))
}

private fun teamInitials(name: String): String = name.trim().split(Regex("\\s+")).filter { it.isNotBlank() }.take(2).joinToString("") { it.first().uppercase() }

private fun formatTime(utc: String): String = runCatching { OffsetDateTime.parse(utc).atZoneSameInstant(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("M/d h:mm a")) }.getOrDefault("UPCOMING")
