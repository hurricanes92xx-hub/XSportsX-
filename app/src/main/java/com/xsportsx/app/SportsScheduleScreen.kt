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
            loading = true; error = null
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
                Text("ESPN + official league and combat-event feeds", color = Color(0xFF858B98), fontSize = 12.sp)
            }
            TextButton(onClick = { refresh() }) { Text("REFRESH") }
        }
        Row(Modifier.padding(horizontal = 28.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("ALL", "LIVE", "UPCOMING").forEach { value ->
                FilterChip(selected = filter == value, onClick = { filter = value }, label = { Text(value) })
            }
        }
        when {
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator(color = Color(0xFFFF1744)) }
            error != null -> Box(Modifier.fillMaxSize().padding(30.dp), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("SCHEDULE ERROR", color = Color(0xFFFF536C), fontWeight = FontWeight.Black)
                    Spacer(Modifier.height(8.dp)); Text(error!!, color = Color.White)
                    Spacer(Modifier.height(12.dp)); TextButton(onClick = { refresh() }) { Text("TRY AGAIN") }
                }
            }
            visible.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(if (filter == "LIVE") "Nothing live right now" else "No events found", color = Color(0xFF858B98))
            }
            else -> LazyColumn(contentPadding = PaddingValues(28.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                items(visible, key = { it.id }) { event -> ScheduleEventCard(event) { onEvent(event) } }
            }
        }
    }
}

@Composable
private fun ScheduleEventCard(event: SportsEvent, onClick: () -> Unit) {
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp)).background(Color(0xFF11151D)).clickable { onClick() }
    ) {
        Box(Modifier.fillMaxWidth().height(155.dp).background(Color(0xFF171C26))) {
            if (event.artUrl.isNotBlank()) {
                AsyncImage(model = event.artUrl, contentDescription = event.title, modifier = Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
                Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color.Transparent, Color(0xEE07080C)))))
            } else {
                Box(Modifier.fillMaxSize().background(Brush.linearGradient(listOf(Color(0xFF300914), Color(0xFF10151E), Color(0xFF1D0C08)))))
            }
            Row(Modifier.fillMaxWidth().align(Alignment.BottomStart).padding(16.dp), verticalAlignment = Alignment.Bottom) {
                Column(Modifier.weight(1f)) {
                    Text(event.league.uppercase(), color = Color(0xFFFF536C), fontSize = 10.sp, fontWeight = FontWeight.Black, letterSpacing = 1.5.sp)
                    Text(event.home.ifBlank { event.title }, color = Color.White, fontSize = 19.sp, fontWeight = FontWeight.Black)
                    if (event.away.isNotBlank()) Text(event.away, color = Color.White, fontSize = 17.sp, fontWeight = FontWeight.Bold)
                }
                if (event.isLive) {
                    Surface(color = Color(0xFFFF1744), shape = RoundedCornerShape(9.dp)) { Text("● LIVE", color = Color.White, modifier = Modifier.padding(horizontal = 9.dp, vertical = 6.dp), fontSize = 10.sp, fontWeight = FontWeight.Black) }
                }
            }
        }
        Row(Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(if (event.isLive) "LIVE NOW" else formatTime(event.startUtc), color = if (event.isLive) Color(0xFFFF1744) else Color(0xFFB8BEC8), fontSize = 11.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.width(12.dp))
            Text(event.status.ifBlank { event.broadcast }.ifBlank { "EVENT" }, color = Color(0xFF7F8794), fontSize = 10.sp, modifier = Modifier.weight(1f))
            Text("VIEW CARD →", color = Color(0xFFFF1744), fontSize = 10.sp, fontWeight = FontWeight.Black)
        }
    }
}

private fun formatTime(utc: String): String = runCatching {
    OffsetDateTime.parse(utc).atZoneSameInstant(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("M/d h:mm a"))
}.getOrDefault("UPCOMING")
