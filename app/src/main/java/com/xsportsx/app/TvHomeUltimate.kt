package com.xsportsx.app

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.async

private val TvUltimateRed = Color(0xFFFF1838)
private val TvUltimateBlue = Color(0xFF2E8BFF)
private val TvUltimateBg = Color(0xFF03060B)
private val TvUltimatePanel = Color(0xFF0B111A)
private val TvUltimateMuted = Color(0xFF8993A2)

private val tvUltimateSports = (SportsScheduleService.uiLeagueChoices + listOf("WWE", "AEW", "TNA", "Monster Jam"))
    .distinctBy { SportsScheduleService.canonicalLeagueFor(it) }

@Composable
fun TvHomeUltimate(onConnect: () -> Unit = {}, onNetwork: (String) -> Unit = {}) {
    var tab by remember { mutableStateOf("HOME") }
    var events by remember { mutableStateOf<List<SportsEvent>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }

    LaunchedEffect(Unit) {
        while (isActive) {
            val result = runCatching {
                coroutineScope {
                    val upcoming = async { ScheduleSnapshotRepository.upcoming() }
                    val live = async { ScheduleSnapshotRepository.live() }
                    (upcoming.await() + live.await())
                }
            }.getOrDefault(emptyList())
            if (result.isNotEmpty()) {
                events = result.distinctBy { it.id.ifBlank { "${it.league}|${it.away}|${it.home}|${it.startUtc}" } }
            }
            loading = events.isEmpty()
            delay(30_000L)
        }
    }

    val live = events.filter { it.isLive }
    val upcoming = events.filter { !it.isLive && (it.isPregame() || it.isUpcoming) }.take(100)

    Row(Modifier.fillMaxSize().background(TvUltimateBg)) {
        TvUltimateRail(tab, onSelect = { tab = it }, onNetwork = onNetwork)
        LazyColumn(
            modifier = Modifier.weight(1f).fillMaxHeight(),
            contentPadding = PaddingValues(start = 24.dp, end = 30.dp, top = 22.dp, bottom = 80.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp)
        ) {
            item {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("XSPORTSX", color = Color.White, fontSize = 28.sp, fontWeight = FontWeight.Black, letterSpacing = 2.sp)
                        Text("LIVE SPORTS COMMAND CENTER", color = TvUltimateMuted, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                    }
                    TvUltimateButton("⚙ SETTINGS") { onConnect() }
                }
            }
            when (tab) {
                "LIVE" -> { item { TvUltimateSection("LIVE NOW", "${live.size} LIVE") }; item { if (live.isEmpty()) TvUltimateEmpty(if (loading) "CHECKING LIVE SPORTS…" else "NO LIVE GAMES RIGHT NOW") else TvUltimateEventRow(live, onNetwork) } }
                "UPCOMING" -> { item { TvUltimateSection("UPCOMING", "${upcoming.size} EVENTS • NEXT 3 DAYS") }; item { if (upcoming.isEmpty()) TvUltimateEmpty(if (loading) "LOADING UPCOMING…" else "NO UPCOMING EVENTS FOUND") else TvUltimateEventRow(upcoming, onNetwork) } }
                else -> {
                    item { TvUltimateHero(onClick = { tab = "LIVE" }) }
                    item { TvUltimateSection("LIVE NOW", "${live.size} LIVE • SHARED FEED") }
                    item { if (live.isEmpty()) TvUltimateEmpty(if (loading) "CHECKING LIVE SPORTS…" else "NO LIVE GAMES RIGHT NOW") else TvUltimateEventRow(live, onNetwork) }
                    item { TvUltimateSection("UPCOMING", "${upcoming.size} EVENTS • NEXT 3 DAYS") }
                    item { if (upcoming.isEmpty()) TvUltimateEmpty(if (loading) "LOADING UPCOMING…" else "NO UPCOMING EVENTS FOUND") else TvUltimateEventRow(upcoming, onNetwork) }
                    item { TvUltimateSection("TOP SPORTS", "${tvUltimateSports.size} LEAGUE CENTERS") }
                    item { TvUltimateSportRow(onNetwork) }
                    item { TvUltimateSection("SPORTS NETWORKS", "LIVE SOURCES") }
                    item { TvUltimateNetworkRow(onNetwork) }
                }
            }
        }
    }
}

@Composable private fun TvUltimateRail(tab: String, onSelect: (String) -> Unit, onNetwork: (String) -> Unit) {
    Column(Modifier.width(205.dp).fillMaxHeight().background(Brush.horizontalGradient(listOf(Color(0xFF071019), TvUltimateBg))).padding(20.dp)) {
        Text("X", color = TvUltimateRed, fontSize = 38.sp, fontWeight = FontWeight.Black)
        Text("XSPORTSX", color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Black)
        Spacer(Modifier.height(22.dp))
        TvUltimateRailItem("HOME", tab == "HOME") { onSelect("HOME") }
        TvUltimateRailItem("LIVE NOW", tab == "LIVE") { onSelect("LIVE") }
        TvUltimateRailItem("UPCOMING", tab == "UPCOMING") { onSelect("UPCOMING") }
        Spacer(Modifier.height(18.dp))
        Text("SPORTS", color = TvUltimateMuted, fontSize = 9.sp, fontWeight = FontWeight.Black, letterSpacing = 1.3.sp)
        Spacer(Modifier.height(6.dp))
        tvUltimateSports.forEach { league -> Row(Modifier.fillMaxWidth().clickable { onNetwork("LEAGUE:$league") }.padding(vertical = 3.dp), verticalAlignment = Alignment.CenterVertically) { XSportsLeagueLogo(league, Modifier.size(34.dp), 34.dp); Spacer(Modifier.width(8.dp)); Text(league, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis) } }
        Spacer(Modifier.weight(1f))
        Text("TV MODE", color = Color(0xFF596371), fontSize = 10.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable private fun TvUltimateRailItem(text: String, active: Boolean, blue: Boolean = false, onClick: () -> Unit) {
    Text(text, color = Color.White, fontSize = 10.sp, fontWeight = if (active) FontWeight.Black else FontWeight.Bold,
        modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp).background(if (active) Color(0xFF241018) else Color.Transparent, RoundedCornerShape(10.dp)).border(1.dp, if (active) TvUltimateRed else Color.Transparent, RoundedCornerShape(10.dp)).clickable { onClick() }.padding(horizontal = 10.dp, vertical = 8.dp))
}

@Composable private fun TvUltimateHero(onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().height(145.dp).background(Brush.horizontalGradient(listOf(Color(0xFF190810), Color(0xFF101824), Color(0xFF08121D))), RoundedCornerShape(18.dp)).border(1.dp, TvUltimateRed.copy(alpha = .28f), RoundedCornerShape(18.dp)).clickable { onClick() }.padding(24.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text("LIVE SPORTS", color = TvUltimateRed, fontSize = 11.sp, fontWeight = FontWeight.Black, letterSpacing = 2.sp)
            Text("THE GAME IS ON.", color = Color.White, fontSize = 32.sp, fontWeight = FontWeight.Black)
            Text("Every league • live events • full 3-day schedule", color = TvUltimateMuted, fontSize = 11.sp, fontWeight = FontWeight.Bold)
        }
        Text("▶", color = TvUltimateRed, fontSize = 60.sp, fontWeight = FontWeight.Black)
    }
}

@Composable private fun TvUltimateSection(title: String, subtitle: String) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Bottom) { Text(title, color = Color.White, fontSize = 19.sp, fontWeight = FontWeight.Black); Spacer(Modifier.width(10.dp)); Text(subtitle, color = TvUltimateMuted, fontSize = 9.sp, fontWeight = FontWeight.Bold) }
}

@Composable private fun TvUltimateEventRow(events: List<SportsEvent>, onNetwork: (String) -> Unit) {
    LazyRow(horizontalArrangement = Arrangement.spacedBy(12.dp), contentPadding = PaddingValues(bottom = 3.dp)) {
        items(events, key = { "${it.id}|${it.startUtc}" }) { event ->
            Column(Modifier.width(260.dp).height(138.dp).background(TvUltimatePanel, RoundedCornerShape(16.dp)).border(1.dp, if (event.isLive) TvUltimateRed.copy(alpha = .65f) else TvUltimateBlue.copy(alpha = .22f), RoundedCornerShape(16.dp)).clickable { onNetwork(event.broadcast.ifBlank { "${event.league} ${event.away} ${event.home}" }) }.padding(14.dp)) {
                Row(Modifier.fillMaxWidth()) { Text(event.league, color = TvUltimateBlue, fontSize = 9.sp, fontWeight = FontWeight.Black); Spacer(Modifier.weight(1f)); Text(if (event.isLive) "● LIVE" else "UPCOMING", color = if (event.isLive) TvUltimateRed else TvUltimateMuted, fontSize = 8.sp, fontWeight = FontWeight.Black) }
                Spacer(Modifier.height(9.dp)); Text(event.away.ifBlank { "TBD" }, color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis); Text("@ ${event.home.ifBlank { "TBD" }}", color = Color(0xFFB6BDCA), fontSize = 12.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis); Spacer(Modifier.height(8.dp)); Text(if (event.isLive) event.status.ifBlank { "LIVE" } else event.broadcast.ifBlank { "SCHEDULED" }, color = TvUltimateMuted, fontSize = 9.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
    }
}

@Composable private fun TvUltimateSportRow(onNetwork: (String) -> Unit) {
    LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(bottom = 3.dp)) {
        items(tvUltimateSports) { league -> Column(Modifier.width(142.dp).height(106.dp).background(TvUltimatePanel, RoundedCornerShape(14.dp)).border(1.dp, TvUltimateBlue.copy(alpha = .28f), RoundedCornerShape(14.dp)).clickable { onNetwork("LEAGUE:$league") }.padding(10.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) { XSportsLeagueLogo(league, Modifier.size(54.dp), 54.dp); Spacer(Modifier.height(5.dp)); Text(league, color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis) } }
    }
}

@Composable private fun TvUltimateNetworkRow(onNetwork: (String) -> Unit) {
    val networks = listOf("ESPN", "ESPN2", "ESPNU", "NFL NETWORK", "FS1", "CBS SPORTS", "SEC NETWORK", "ACC NETWORK", "BIG TEN NETWORK", "ESPN+")
    LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) { items(networks) { network -> Column(Modifier.width(116.dp).height(92.dp).background(TvUltimatePanel, RoundedCornerShape(14.dp)).border(1.dp, TvUltimateRed.copy(alpha = .3f), RoundedCornerShape(14.dp)).clickable { onNetwork(network) }.padding(8.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) { XSportsNetworkLogo(network, Modifier.size(46.dp), 46.dp); Spacer(Modifier.height(5.dp)); Text(network, color = Color.White, fontSize = 8.sp, fontWeight = FontWeight.Black, maxLines = 1, overflow = TextOverflow.Ellipsis) } } }
}

@Composable private fun TvUltimateButton(text: String, onClick: () -> Unit) { Text(text, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black, modifier = Modifier.background(Color(0xFF101722), RoundedCornerShape(11.dp)).border(1.dp, TvUltimateRed.copy(alpha = .3f), RoundedCornerShape(11.dp)).clickable { onClick() }.padding(horizontal = 12.dp, vertical = 9.dp)) }

@Composable private fun TvUltimateEmpty(text: String) { Box(Modifier.fillMaxWidth().height(125.dp).background(TvUltimatePanel, RoundedCornerShape(16.dp)), contentAlignment = Alignment.Center) { Text(text, color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Black) } }
