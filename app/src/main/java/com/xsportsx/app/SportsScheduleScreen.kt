package com.xsportsx.app

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
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

@Composable
fun SportsScheduleScreen(initialLeague: String? = null, onBack: () -> Unit, onEvent: (SportsEvent) -> Unit) {
    val scope = rememberCoroutineScope()
    var events by remember { mutableStateOf<List<SportsEvent>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var filter by remember { mutableStateOf("ALL") }
    var leagueFilter by remember { mutableStateOf(initialLeague ?: "ALL") }

    fun refresh(force: Boolean = false) {
        scope.launch {
            loading = true
            error = null
            runCatching {
                val upcoming = ScheduleSnapshotRepository.upcoming(if (leagueFilter == "ALL") null else leagueFilter, force)
                val live = ScheduleSnapshotRepository.live(force)
                (upcoming + live).distinctBy { "${it.league}|${it.away}|${it.home}|${it.startUtc.take(16)}" }
            }
                .onSuccess { events = it }
                .onFailure { error = it.message ?: "Unable to load schedules" }
            loading = false
        }
    }

    LaunchedEffect(initialLeague) {
        leagueFilter = initialLeague ?: "ALL"
        refresh(false)
    }

    val statusVisible = when (filter) {
        "LIVE" -> events.filter { it.isLive }
        "UPCOMING" -> events.filter { !it.isLive && (it.isUpcoming || it.isPregame()) }
        else -> events
    }
    val visible = if (leagueFilter == "ALL") statusVisible else statusVisible.filter { SportsScheduleService.canonicalLeagueFor(it.league) == SportsScheduleService.canonicalLeagueFor(leagueFilter) }
    val leagueChoices = listOf("ALL") + SportsScheduleService.uiLeagueChoices + listOf("WWE", "AEW", "TNA", "Monster Jam")
        .distinctBy { SportsScheduleService.canonicalLeagueFor(it) }

    Column(Modifier.fillMaxSize().background(Color(0xFF07080C))) {
        Row(Modifier.fillMaxWidth().padding(28.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("‹", color = Color.White, fontSize = 38.sp, modifier = Modifier.clickable { onBack() })
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text(if (leagueFilter == "ALL") "LIVE + UPCOMING" else SportsScheduleService.canonicalLeagueFor(leagueFilter), color = Color.White, fontSize = 28.sp, fontWeight = FontWeight.Black)
                Text(if (leagueFilter == "ALL") "Sports schedule • NEXT 3 DAYS" else "${SportsScheduleService.canonicalLeagueFor(leagueFilter)} • NEXT 3 DAYS", color = Color(0xFF858B98), fontSize = 12.sp)
            }
            TextButton(onClick = { refresh(true) }) { Text("REFRESH") }
        }
        Row(Modifier.padding(horizontal = 28.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("ALL", "LIVE", "UPCOMING").forEach { value -> FilterChip(selected = filter == value, onClick = { filter = value }, label = { Text(value) }) }
        }
        LazyRow(
            modifier = Modifier.fillMaxWidth(),
            contentPadding = PaddingValues(horizontal = 28.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(leagueChoices) { league ->
                FilterChip(
                    selected = leagueFilter.equals(league, true),
                    onClick = { leagueFilter = league; refresh(false) },
                    label = { Text(league) }
                )
            }
        }
        when {
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator(color = Color(0xFFFF1744)) }
            error != null -> Box(Modifier.fillMaxSize().padding(30.dp), contentAlignment = Alignment.Center) { Column(horizontalAlignment = Alignment.CenterHorizontally) { Text("SCHEDULE ERROR", color = Color(0xFFFF536C), fontWeight = FontWeight.Black); Spacer(Modifier.height(8.dp)); Text(error!!, color = Color.White); Spacer(Modifier.height(12.dp)); TextButton(onClick = { refresh(true) }) { Text("TRY AGAIN") } } }
            visible.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text(if (filter == "LIVE") "Nothing live right now" else if (leagueFilter == "ALL") "No events found" else "No ${SportsScheduleService.canonicalLeagueFor(leagueFilter)} events found in the next 3 days", color = Color(0xFF858B98)) }
            else -> LazyColumn(contentPadding = PaddingValues(28.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) { items(visible, key = { it.id.ifBlank { "${it.league}|${it.home}|${it.away}|${it.startUtc}" } }) { event -> ScheduleEventCard(event) { onEvent(event) } } }
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
                Text(if (event.isLive) "LIVE NOW" else event.startUtc, color = if (event.isLive) Color(0xFFFF1744) else Color(0xFFB8BEC8), fontSize = 11.sp, fontWeight = FontWeight.Bold)
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
            Box(Modifier.clip(RoundedCornerShape(10.dp)).background(Color(0xE90B1018)).padding(horizontal = 10.dp, vertical = 7.dp)) { Text("VS", color = Color.White, fontSize = 16.sp, fontWeight = FontWeight.Black, letterSpacing = 1.2.sp) }
            Spacer(Modifier.height(5.dp)); Text(event.league.uppercase(), color = Color(0xFFFF536C), fontSize = 8.sp, fontWeight = FontWeight.Black, letterSpacing = 1.sp)
        }
        TeamLogo(event.awayLogo, event.away.ifBlank { "AWAY" }, event.league, 76.dp)
    }
}

@Composable private fun TeamLogo(url: String, name: String, league: String, size: androidx.compose.ui.unit.Dp) {
    val fallbackUrl = remember(name, league) { espnTeamLogoUrl(name, league) }
    var currentUrl by remember(url, name, league) { mutableStateOf(url.ifBlank { fallbackUrl.orEmpty() }) }
    var failed by remember(url, name, league) { mutableStateOf(false) }
    Box(Modifier.size(size).clip(CircleShape).background(Brush.radialGradient(listOf(Color(0xFF273446), Color(0xFF0A0F17)))), contentAlignment = Alignment.Center) {
        if (currentUrl.isNotBlank() && !failed) AsyncImage(model = currentUrl, contentDescription = name, modifier = Modifier.fillMaxSize().padding(8.dp), contentScale = ContentScale.Fit, onError = { if (fallbackUrl != null && currentUrl != fallbackUrl) currentUrl = fallbackUrl else failed = true })
        else Text(teamInitials(name), color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.Black)
    }
}

private fun espnTeamLogoUrl(name: String, league: String): String? {
    val n = name.trim().lowercase()
    if (n.isBlank() || n == "home" || n == "away") return null
    val code = when {
        n.length in 2..4 && n.all { it.isLetter() } -> n
        n.contains("yankees") -> "nyy"; n.contains("astros") -> "hou"; n.contains("blue jays") -> "tor"; n.contains("mariners") -> "sea"
        n.contains("lakers") -> "lal"; n.contains("celtics") -> "bos"; n.contains("knicks") -> "ny"
        n.contains("buffalo") || n.contains("bills") -> "buf"; n.contains("kansas city") || n.contains("chiefs") -> "kc"
        n.contains("miami") -> "mia"; n.contains("new york giants") -> "nyg"; n.contains("new york jets") -> "nyj"
        n.contains("philadelphia") || n.contains("eagles") -> "phi"; n.contains("dallas") || n.contains("cowboys") -> "dal"
        n.contains("san francisco") || n.contains("49ers") -> "sf"; n.contains("seattle") || n.contains("seahawks") -> "sea"
        else -> return null
    }
    val sport = when { league.equals("NFL", true) -> "nfl"; league.equals("NBA", true) -> "nba"; league.equals("MLB", true) -> "mlb"; league.equals("NHL", true) -> "nhl"; else -> return null }
    return "https://a.espncdn.com/i/teamlogos/$sport/500/scoreboard/$code.png"
}

@Composable private fun EventArtBadge(event: SportsEvent, combat: Boolean, racing: Boolean, modifier: Modifier = Modifier) {
    Box(modifier.size(112.dp).clip(RoundedCornerShape(24.dp)).background(Color(0xD90A0D13)), contentAlignment = Alignment.Center) { Text(if (event.league.equals("UFC", true)) "UFC" else if (racing) "F1" else "BOXING", color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Black, letterSpacing = 1.4.sp) }
}

private fun cardBrush(event: SportsEvent, combat: Boolean, racing: Boolean): Brush = when {
    combat -> Brush.horizontalGradient(listOf(Color(0xFF1A0710), Color(0xFF0D1017)))
    racing -> Brush.horizontalGradient(listOf(Color(0xFF10151E), Color(0xFF160B0B)))
    event.isLive -> Brush.horizontalGradient(listOf(Color(0xFF1B0A11), Color(0xFF0B111A)))
    else -> Brush.horizontalGradient(listOf(Color(0xFF101722), Color(0xFF0A0E15)))
}

private fun teamInitials(name: String): String = name.trim().split(Regex("\\s+")).filter { it.isNotBlank() }.take(2).joinToString("") { it.first().uppercase() }.ifBlank { "?" }
