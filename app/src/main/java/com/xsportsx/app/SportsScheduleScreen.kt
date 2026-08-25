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
    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(24.dp)).background(Color(0xFF0A0E15)).clickable { onClick() }) {
        Box(Modifier.fillMaxWidth().height(if (combat || racing) 196.dp else 184.dp).background(cardBrush(event, combat, racing))) {
            if (art.isNotBlank()) {
                AsyncImage(model = art, contentDescription = null, modifier = Modifier.fillMaxSize(), contentScale = ContentScale.Crop, alpha = 0.34f)
                Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color.Transparent, Color(0xE8070A10)))))
            }
            if (combat || racing) {
                Column(Modifier.align(Alignment.TopStart).padding(18.dp)) {
                    Text(when { event.league.equals("UFC", true) -> "UFC • FIGHT EVENT"; event.league.equals("BOXING", true) -> "BOXING • EVENT NIGHT"; else -> "F1 • GRAND PRIX" }, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black, letterSpacing = 1.4.sp)
                    Spacer(Modifier.height(5.dp)); Text(event.title.ifBlank { event.league }, color = Color.White, fontSize = 22.sp, fontWeight = FontWeight.Black)
                }
                EventArtBadge(event, combat, racing, Modifier.align(Alignment.Center))
            } else LogoVsLogo(event, Modifier.align(Alignment.Center))
            Surface(color = if (event.isLive) Color(0xFFFF1744) else Color(0xE60A0D13), shape = RoundedCornerShape(10.dp), modifier = Modifier.align(Alignment.TopEnd).padding(14.dp)) {
                Text(if (event.isLive) "● LIVE" else event.league.uppercase(), color = Color.White, modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp), fontSize = 9.sp, fontWeight = FontWeight.Black)
            }
        }
        Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 15.dp), verticalAlignment = Alignment.CenterVertically) {
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
        TeamLogo(event.homeLogo, event.home.ifBlank { "HOME" }, event.league, 76.dp)
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(horizontal = 14.dp)) {
            Box(Modifier.clip(RoundedCornerShape(10.dp)).background(Color(0xE90B1018)).padding(horizontal = 10.dp, vertical = 7.dp)) {
                Text("VS", color = Color.White, fontSize = 16.sp, fontWeight = FontWeight.Black, letterSpacing = 1.2.sp)
            }
            Spacer(Modifier.height(5.dp))
            Text(event.league.uppercase(), color = Color(0xFFFF536C), fontSize = 8.sp, fontWeight = FontWeight.Black, letterSpacing = 1.sp)
        }
        TeamLogo(event.awayLogo, event.away.ifBlank { "AWAY" }, event.league, 76.dp)
    }
}

@Composable
private fun TeamLogo(url: String, name: String, league: String, size: androidx.compose.ui.unit.Dp) {
    val fallbackUrl = remember(name, league) { espnTeamLogoUrl(name, league) }
    var currentUrl by remember(url, name, league) { mutableStateOf(url.ifBlank { fallbackUrl.orEmpty() }) }
    var failed by remember(url, name, league) { mutableStateOf(false) }
    Box(Modifier.size(size).clip(CircleShape).background(Brush.radialGradient(listOf(Color(0xFF273446), Color(0xFF0A0F17)))), contentAlignment = Alignment.Center) {
        if (currentUrl.isNotBlank() && !failed) {
            AsyncImage(model = currentUrl, contentDescription = name, modifier = Modifier.fillMaxSize().padding(8.dp), contentScale = ContentScale.Fit, onError = {
                if (fallbackUrl != null && currentUrl != fallbackUrl) currentUrl = fallbackUrl else failed = true
            })
        } else {
            Text(teamInitials(name), color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.Black)
        }
    }
}

private fun espnTeamLogoUrl(name: String, league: String): String? {
    val n = name.trim().lowercase()
    if (n.isBlank() || n == "home" || n == "away") return null
    val code = when {
        n.length in 2..4 && n.all { it.isLetter() } -> n
        n.contains("arizona") || n.contains("cardinals") -> "ari"
        n.contains("atlanta") || n.contains("falcons") -> "atl"
        n.contains("baltimore") || n.contains("ravens") -> "bal"
        n.contains("buffalo") || n.contains("bills") -> "buf"
        n.contains("carolina") || n.contains("panthers") -> "car"
        n.contains("chicago") || n.contains("bears") -> "chi"
        n.contains("cincinnati") || n.contains("bengals") -> "cin"
        n.contains("cleveland") || n.contains("browns") -> "cle"
        n.contains("dallas") || n.contains("cowboys") -> "dal"
        n.contains("denver") || n.contains("broncos") -> "den"
        n.contains("detroit") || n.contains("lions") -> "det"
        n.contains("green bay") || n.contains("packers") -> "gb"
        n.contains("houston") || n.contains("texans") -> "hou"
        n.contains("indianapolis") || n.contains("colts") -> "ind"
        n.contains("jacksonville") || n.contains("jaguars") -> "jax"
        n.contains("kansas city") || n.contains("chiefs") -> "kc"
        n.contains("las vegas") || n.contains("raiders") -> "lv"
        n.contains("chargers") -> "lac"
        n.contains("rams") -> "lar"
        n.contains("miami") || n.contains("dolphins") -> "mia"
        n.contains("minnesota") || n.contains("vikings") -> "min"
        n.contains("new england") || n.contains("patriots") -> "ne"
        n.contains("new orleans") || n.contains("saints") -> "no"
        n.contains("new york giants") || n.contains("giants") -> "nyg"
        n.contains("new york jets") || n.contains("jets") -> "nyj"
        n.contains("philadelphia") || n.contains("eagles") -> "phi"
        n.contains("pittsburgh") || n.contains("steelers") -> "pit"
        n.contains("san francisco") || n.contains("49ers") -> "sf"
        n.contains("seattle") || n.contains("seahawks") -> "sea"
        n.contains("tampa bay") || n.contains("buccaneers") -> "tb"
        n.contains("tennessee") || n.contains("titans") -> "ten"
        n.contains("washington") || n.contains("commanders") -> "wsh"
        n.contains("lakers") -> "lal"
        n.contains("celtics") -> "bos"
        n.contains("knicks") -> "ny"
        n.contains("yankees") -> "nyy"
        n.contains("astros") -> "hou"
        n.contains("blue jays") -> "tor"
        n.contains("mariners") -> "sea"
        else -> return null
    }
    val sport = when {
        league.equals("NFL", true) -> "nfl"
        league.equals("NBA", true) -> "nba"
        league.equals("MLB", true) -> "mlb"
        league.equals("NHL", true) -> "nhl"
        else -> return null
    }
    return "https://a.espncdn.com/i/teamlogos/$sport/500/scoreboard/$code.png"
}


@Composable
private fun EventArtBadge(event: SportsEvent, combat: Boolean, racing: Boolean, modifier: Modifier = Modifier) {
    val isUfc = combat && event.league.equals("UFC", true)
    Box(modifier.size(112.dp).clip(RoundedCornerShape(24.dp)).background(Color(0xD90A0D13)), contentAlignment = Alignment.Center) {
        androidx.compose.foundation.Canvas(Modifier.fillMaxSize().padding(10.dp)) {
            val cx = size.width / 2f
            val cy = size.height / 2f
            if (isUfc) {
                val r = size.minDimension * .34f
                val pts = (0 until 8).map { i ->
                    val a = Math.PI / 8.0 + i * Math.PI / 4.0
                    androidx.compose.ui.geometry.Offset(cx + (r * kotlin.math.cos(a)).toFloat(), cy + (r * kotlin.math.sin(a)).toFloat())
                }
                for (i in pts.indices) drawLine(Color(0xFFFF1744), pts[i], pts[(i + 1) % pts.size], strokeWidth = 5f)
                drawCircle(Color(0x33FF1744), r * .62f)
                drawLine(Color.White, androidx.compose.ui.geometry.Offset(cx - r * .55f, cy), androidx.compose.ui.geometry.Offset(cx + r * .55f, cy), strokeWidth = 3f)
            } else {
                val left = size.width * .18f
                val right = size.width * .82f
                val top = size.height * .28f
                val bottom = size.height * .72f
                drawLine(Color(0xFFFF6D00), androidx.compose.ui.geometry.Offset(left, top), androidx.compose.ui.geometry.Offset(right, top), strokeWidth = 4f)
                drawLine(Color(0xFFFF1744), androidx.compose.ui.geometry.Offset(left, (top + bottom) / 2f), androidx.compose.ui.geometry.Offset(right, (top + bottom) / 2f), strokeWidth = 4f)
                drawLine(Color.White, androidx.compose.ui.geometry.Offset(left, bottom), androidx.compose.ui.geometry.Offset(right, bottom), strokeWidth = 4f)
                drawLine(Color(0xFF7F8794), androidx.compose.ui.geometry.Offset(left, top - 8f), androidx.compose.ui.geometry.Offset(left, bottom + 8f), strokeWidth = 6f)
                drawLine(Color(0xFF7F8794), androidx.compose.ui.geometry.Offset(right, top - 8f), androidx.compose.ui.geometry.Offset(right, bottom + 8f), strokeWidth = 6f)
                drawCircle(Color(0x33FFFF00), 11f, androidx.compose.ui.geometry.Offset(cx - 12f, cy - 2f))
                drawCircle(Color(0x33FF1744), 11f, androidx.compose.ui.geometry.Offset(cx + 12f, cy + 2f))
            }
        }
        Text(if (isUfc) "UFC" else "BOXING", color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Black, letterSpacing = 1.4.sp)
    }
}


private fun cardBrush(event: SportsEvent, combat: Boolean, racing: Boolean): Brush = when {
    racing -> Brush.linearGradient(listOf(Color(0xFF120B14), Color(0xFF111A2B), Color(0xFF29080E)))
    combat && event.league.equals("UFC", true) -> Brush.linearGradient(listOf(Color(0xFF28070D), Color(0xFF10141C), Color(0xFF3A1010)))
    combat -> Brush.linearGradient(listOf(Color(0xFF29100A), Color(0xFF15141A), Color(0xFF3A0A18)))
    else -> Brush.linearGradient(listOf(Color(0xFF280712), Color(0xFF101722), Color(0xFF251008)))
}

private fun teamInitials(name: String): String = name.trim().split(Regex("\\s+")).filter { it.isNotBlank() }.take(2).joinToString("") { it.first().uppercase() }

private fun formatTime(utc: String): String = runCatching { OffsetDateTime.parse(utc).atZoneSameInstant(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("M/d h:mm a")) }.getOrDefault("UPCOMING")
