package com.xsportsx.app

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil3.compose.AsyncImage
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive

private val FxRed = Color(0xFFFF1838)
private val FxBlue = Color(0xFF2E8BFF)
private val FxBg = Color(0xFF03060B)
private val FxPanel = Color(0xFF0B111A)
private val FxMuted = Color(0xFF8993A2)

private val fxSports = listOf("NFL" to "NFL", "NBA" to "NBA", "NCAA FB" to "NCAA", "NCAA BB" to "NCAA", "MLB" to "MLB", "NHL" to "NHL", "UFC" to "UFC", "BOXING" to "BOX")
private val fxNetworks = listOf("ESPN", "ESPN2", "ESPNU", "NFL NETWORK", "FS1", "CBS SPORTS", "SEC NETWORK", "ACC NETWORK", "BIG TEN NETWORK", "ESPN+")

@Composable
fun TvHomeFixed(onConnect: () -> Unit = {}, onNetwork: (String) -> Unit = {}) {
    var selected by remember { mutableStateOf("HOME") }
    var events by remember { mutableStateOf<List<SportsEvent>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    val scroll = rememberScrollState()

    LaunchedEffect(Unit) {
        while (isActive) {
            loading = events.isEmpty()
            val result = runCatching { SportsScheduleService.load() }.getOrDefault(emptyList())
            if (result.isNotEmpty()) events = result
            loading = false
            delay(60_000L)
        }
    }

    val live = events.filter { it.isLive }.take(30)
    val upcoming = events.filter { it.isPregame() || it.isUpcoming }.filterNot { it.isLive }.take(30)

    Box(Modifier.fillMaxSize().background(FxBg)) {
        Row(Modifier.fillMaxSize()) {
            FxNav(selected) { selected = it }
            Column(Modifier.weight(1f).fillMaxHeight().verticalScroll(scroll).padding(start = 22.dp, end = 30.dp, top = 20.dp, bottom = 72.dp)) {
                FxTopBar { selected = "SETTINGS" }
                Spacer(Modifier.height(14.dp))
                when (selected) {
                    "HOME" -> {
                        FxHero { selected = "LIVE NOW" }
                        Spacer(Modifier.height(18.dp))
                        FxSection("LIVE NOW", if (loading && live.isEmpty()) "LOADING" else "${live.size} LIVE")
                        if (live.isNotEmpty()) FxEventRow(live, onNetwork) else FxEmpty(if (loading) "LOADING LIVE GAMES…" else "NO LIVE GAMES RIGHT NOW")
                        Spacer(Modifier.height(16.dp))
                        FxSection("NEXT GAMES", "${upcoming.size} UPCOMING")
                        if (upcoming.isNotEmpty()) FxEventRow(upcoming.take(12), onNetwork) else FxEmpty("LOADING UPCOMING SCHEDULE…")
                        Spacer(Modifier.height(16.dp))
                        FxSection("TOP SPORTS", "FAST ACCESS")
                        FxTileRow(fxSports) { onNetwork(it) }
                        Spacer(Modifier.height(16.dp))
                        FxSection("SPORTS NETWORKS", "LIVE SOURCES")
                        FxNetworkGrid(onNetwork)
                    }
                    "LIVE NOW" -> {
                        FxSection("LIVE NOW", "${live.size} LIVE")
                        if (live.isNotEmpty()) FxEventRow(live, onNetwork) else FxEmpty(if (loading) "LOADING LIVE GAMES…" else "NO LIVE GAMES RIGHT NOW")
                    }
                    "UPCOMING" -> {
                        FxSection("UPCOMING", "${upcoming.size} EVENTS")
                        if (upcoming.isNotEmpty()) FxEventRow(upcoming, onNetwork) else FxEmpty("NO UPCOMING EVENTS FOUND")
                    }
                    "NETWORKS" -> { FxSection("SPORTS NETWORKS", "LIVE SOURCES"); FxNetworkGrid(onNetwork) }
                    "SETTINGS" -> { FxSection("SETTINGS", "CONNECTION"); FxAction("OPEN CONNECTION SETTINGS", onConnect) }
                    else -> {
                        val filtered = events.filter { it.league.equals(selected, true) }.take(30)
                        FxSection(selected, "LIVE + UPCOMING")
                        if (filtered.isNotEmpty()) FxEventRow(filtered, onNetwork) else FxEmpty("NO EVENTS FOUND")
                    }
                }
            }
        }
        HomeSportsTicker(Modifier.align(Alignment.BottomCenter).fillMaxWidth())
    }
}

@Composable private fun FxNav(selected: String, onSelect: (String) -> Unit) {
    Column(Modifier.width(210.dp).fillMaxHeight().background(Brush.horizontalGradient(listOf(Color(0xFF071019), Color(0xFF04070C)))).padding(start = 22.dp, top = 22.dp, end = 18.dp, bottom = 72.dp)) {
        XtremeLogo(size = 52.dp)
        Text("XSPORTSX", color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Black)
        Spacer(Modifier.height(22.dp))
        listOf("HOME", "LIVE NOW", "UPCOMING", "NETWORKS", "SETTINGS").forEach { label -> FxNavItem(label, selected == label) { onSelect(label) } }
        Spacer(Modifier.height(18.dp))
        Text("SPORTS", color = FxMuted, fontSize = 9.sp, fontWeight = FontWeight.Black, letterSpacing = 1.4.sp)
        Spacer(Modifier.height(6.dp))
        fxSports.forEach { (name, _) -> FxNavItem(name, selected == name, blue = true) { onSelect(name) } }
        Spacer(Modifier.weight(1f))
        Text("TV MODE", color = Color(0xFF596371), fontSize = 10.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable private fun FxNavItem(label: String, active: Boolean, blue: Boolean = false, onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    Row(Modifier.fillMaxWidth().padding(vertical = 3.dp).background(if (active) Color(0xFF1A0B10) else Color.Transparent, RoundedCornerShape(14.dp)).border(1.dp, if (focused || active) (if (blue) FxBlue else FxRed) else Color.Transparent, RoundedCornerShape(14.dp)).onFocusChanged { focused = it.isFocused }.focusable().clickable { onClick() }.padding(horizontal = 13.dp, vertical = 11.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(label, color = Color.White, fontSize = 11.sp, fontWeight = if (focused || active) FontWeight.Black else FontWeight.Bold)
    }
}

@Composable private fun FxTopBar(onSettings: () -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text("XSPORTSX", color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.Black)
        Spacer(Modifier.weight(1f))
        Text("LIVE SPORTS", color = FxMuted, fontSize = 10.sp, fontWeight = FontWeight.Black)
        Spacer(Modifier.width(18.dp))
        FxAction("⚙  Settings", onSettings)
        Spacer(Modifier.width(18.dp))
        Text("TV MODE", color = FxMuted, fontSize = 10.sp, fontWeight = FontWeight.Black)
    }
}

@Composable private fun FxHero(onClick: () -> Unit) {
    Box(Modifier.fillMaxWidth().height(160.dp).background(Brush.horizontalGradient(listOf(Color(0xFF16090F), Color(0xFF101824), Color(0xFF08121D))), RoundedCornerShape(18.dp)).border(1.dp, FxRed.copy(alpha = .28f), RoundedCornerShape(18.dp)).focusable().clickable { onClick() }.padding(24.dp)) {
        Column(Modifier.align(Alignment.CenterStart)) {
            Text("WELCOME TO", color = Color.White, fontSize = 12.sp, letterSpacing = 1.sp)
            Text("XSPORTSX", color = Color.White, fontSize = 34.sp, fontWeight = FontWeight.Black)
            Text("YOUR ULTIMATE SPORTS COMMAND CENTER", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(8.dp))
            Text("REAL LIVE GAMES • LIVE SCORES • NETWORKS", color = FxMuted, fontSize = 10.sp, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable private fun FxSection(title: String, subtitle: String) { Row(Modifier.fillMaxWidth().padding(bottom = 8.dp), verticalAlignment = Alignment.Bottom) { Text(title, color = Color.White, fontSize = 19.sp, fontWeight = FontWeight.Black); Spacer(Modifier.width(10.dp)); Text(subtitle, color = FxMuted, fontSize = 10.sp, fontWeight = FontWeight.Bold) } }

@Composable private fun FxEventRow(events: List<SportsEvent>, onNetwork: (String) -> Unit) {
    LazyRow(horizontalArrangement = Arrangement.spacedBy(12.dp), contentPadding = PaddingValues(bottom = 4.dp)) { items(events, key = { "${it.id}-${it.startUtc}" }) { event -> FxEventCard(event, onNetwork) } }
}

@Composable private fun FxEventCard(event: SportsEvent, onNetwork: (String) -> Unit) {
    var focused by remember { mutableStateOf(false) }
    Column(Modifier.width(270.dp).background(FxPanel, RoundedCornerShape(16.dp)).border(1.dp, if (focused) FxRed else FxRed.copy(alpha = .22f), RoundedCornerShape(16.dp)).onFocusChanged { focused = it.isFocused }.focusable().clickable { onNetwork(event.broadcast.ifBlank { event.league }) }.padding(14.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) { Text(event.league, color = FxBlue, fontSize = 10.sp, fontWeight = FontWeight.Black); Spacer(Modifier.weight(1f)); Text(if (event.isLive) "● LIVE" else "UPCOMING", color = if (event.isLive) FxRed else FxMuted, fontSize = 9.sp, fontWeight = FontWeight.Black) }
        Spacer(Modifier.height(10.dp))
        FxTeam(event.away, event.awayLogo)
        Spacer(Modifier.height(6.dp))
        FxTeam(event.home, event.homeLogo)
        Spacer(Modifier.height(10.dp))
        Text(event.status.ifBlank { event.broadcast }.ifBlank { "SCHEDULED" }, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
        Text(event.broadcast.ifBlank { "LIVE SOURCE MATCHING" }, color = FxMuted, fontSize = 9.sp)
    }
}

@Composable private fun FxTeam(name: String, logo: String) { Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) { if (logo.isNotBlank()) AsyncImage(model = logo, contentDescription = name, modifier = Modifier.size(30.dp), contentScale = ContentScale.Fit) else Box(Modifier.size(30.dp).background(Color(0xFF111923), RoundedCornerShape(8.dp)), contentAlignment = Alignment.Center) { Text(name.take(2), color = Color.White, fontSize = 8.sp, fontWeight = FontWeight.Black) }; Spacer(Modifier.width(9.dp)); Text(name.ifBlank { "TBD" }, Modifier.weight(1f), color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis) } }

@Composable private fun FxTileRow(items: List<Pair<String, String>>, onClick: (String) -> Unit) { LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(bottom = 4.dp)) { items(items, key = { it.first }) { FxTile(it.first, it.second, FxBlue) { onClick(it.first) } } } }

@Composable private fun FxNetworkGrid(onNetwork: (String) -> Unit) { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) { fxNetworks.chunked(5).forEach { row -> Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) { row.forEach { FxTile(it, it.substringBefore(' '), FxRed) { onNetwork(it) } } } } } }

@Composable private fun FxTile(title: String, mark: String, accent: Color, onClick: () -> Unit) { var focused by remember { mutableStateOf(false) }; Column(Modifier.width(120.dp).height(70.dp).background(FxPanel, RoundedCornerShape(14.dp)).border(1.dp, accent.copy(alpha = if (focused) 1f else .25f), RoundedCornerShape(14.dp)).onFocusChanged { focused = it.isFocused }.focusable().clickable { onClick() }.padding(10.dp), verticalArrangement = Arrangement.Center) { Text(mark, color = accent, fontSize = 15.sp, fontWeight = FontWeight.Black); Text(title, color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis) } }

@Composable private fun FxEmpty(text: String) { Box(Modifier.fillMaxWidth().height(170.dp).background(FxPanel, RoundedCornerShape(16.dp)).border(1.dp, FxRed.copy(alpha = .18f), RoundedCornerShape(16.dp)), contentAlignment = Alignment.Center) { Text(text, color = Color.White, fontSize = 15.sp, fontWeight = FontWeight.Black) } }

@Composable private fun FxAction(text: String, onClick: () -> Unit) { var focused by remember { mutableStateOf(false) }; Box(Modifier.background(if (focused) Color(0xFF241018) else Color.Transparent, RoundedCornerShape(14.dp)).border(1.dp, FxRed.copy(alpha = if (focused) 1f else .35f), RoundedCornerShape(14.dp)).onFocusChanged { focused = it.isFocused }.focusable().clickable { onClick() }.padding(horizontal = 12.dp, vertical = 9.dp)) { Text(text, color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.Bold) } }
