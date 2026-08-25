package com.xsportsx.app

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val XcRed = Color(0xFFFF1744)
private val XcPanel = Color(0xFF0D1119)
private val XcPanel2 = Color(0xFF151C27)
private val XcMuted = Color(0xFF7F8998)
private val xcSports = listOf("NFL", "NBA", "WNBA", "MLB", "NHL", "NCAA FB", "NCAA BB", "UFC", "BOXING", "SOCCER")

@Composable
fun XtremeCommandCenterMobile(sourceReady: Boolean, onConnect: () -> Unit) {
    var query by remember { mutableStateOf("") }
    var favorites by remember { mutableStateOf(setOf<String>()) }
    val filtered = xcSports.filter { query.isBlank() || it.contains(query.trim(), ignoreCase = true) }
    Column(Modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("COMMAND CENTER", color = Color.White, fontSize = 16.sp, fontWeight = FontWeight.Black, letterSpacing = 1.6.sp)
                Text("SEARCH • FAVORITES • NEWS • NETWORKS", color = XcMuted, fontSize = 8.sp, fontWeight = FontWeight.Black, letterSpacing = 1.sp)
            }
            Box(Modifier.clip(RoundedCornerShape(12.dp)).background(if (sourceReady) Color(0x2219FF72) else Color(0x22FF1744)).padding(horizontal = 10.dp, vertical = 7.dp)) {
                Text(if (sourceReady) "● FEEDS READY" else "● SOURCE OFFLINE", color = if (sourceReady) Color(0xFF62FF9B) else XcRed, fontSize = 8.sp, fontWeight = FontWeight.Black)
            }
        }
        Spacer(Modifier.height(10.dp))
        TextField(value = query, onValueChange = { query = it }, singleLine = true, placeholder = { Text("Search teams, leagues, UFC, networks…", color = XcMuted, fontSize = 11.sp) }, colors = TextFieldDefaults.colors(focusedContainerColor = XcPanel, unfocusedContainerColor = XcPanel, focusedTextColor = Color.White, unfocusedTextColor = Color.White, focusedIndicatorColor = XcRed, unfocusedIndicatorColor = Color.Transparent), modifier = Modifier.fillMaxWidth().height(54.dp), shape = RoundedCornerShape(15.dp))
        Spacer(Modifier.height(12.dp))
        XcSection("MY SPORTS", "TAP TO PIN")
        Spacer(Modifier.height(7.dp))
        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp), contentPadding = PaddingValues(end = 8.dp)) {
            items(filtered) { sport ->
                val favorite = favorites.contains(sport)
                Box(Modifier.clip(RoundedCornerShape(13.dp)).background(if (favorite) Color(0x332B9BFF) else XcPanel2).border(1.dp, if (favorite) Color(0xFF2E8BFF) else Color.Transparent, RoundedCornerShape(13.dp)).clickable { favorites = if (favorite) favorites - sport else favorites + sport }.padding(horizontal = 12.dp, vertical = 9.dp)) {
                    Text(if (favorite) "★ $sport" else sport, color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Black)
                }
            }
        }
        Spacer(Modifier.height(14.dp))
        XcSection("SPORTS NEWS", "LATEST HEADLINES")
        XcInfoCard("NEWS", "Latest sports headlines stay separate from live-game cards", "NEWS • SCORES • UPDATES", sourceReady, onConnect)
        Spacer(Modifier.height(8.dp))
        XcSection("NETWORK HEALTH", "SOURCE MATCH")
        XcInfoCard("READY", "ESPN • ACC • SEC • NFL NETWORK • FS1 • CBS SPORTS", "NETWORKS", sourceReady, onConnect)
        Spacer(Modifier.height(8.dp))
        XcSection("FAVORITES", "YOUR TEAMS & LEAGUES")
        if (favorites.isEmpty()) XcInfoCard("★", "Pin leagues above to build your personal sports view", "MY SPORTS", sourceReady, onConnect)
        else Text(favorites.joinToString("  •  "), color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable
fun XtremeCommandCenterTv(liveCount: Int, onConnect: () -> Unit) {
    var query by remember { mutableStateOf("") }
    var favorites by remember { mutableStateOf(setOf<String>()) }
    val filtered = xcSports.filter { query.isBlank() || it.contains(query.trim(), ignoreCase = true) }
    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Brush.horizontalGradient(listOf(Color(0xFF0B1018), Color(0xFF151018)))).border(1.dp, XcRed.copy(alpha = .24f), RoundedCornerShape(18.dp)).padding(18.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("XTREME COMMAND CENTER", color = Color.White, fontSize = 22.sp, fontWeight = FontWeight.Black, letterSpacing = 1.5.sp)
                Text("SEARCH • FAVORITES • NEWS • NETWORKS", color = XcMuted, fontSize = 9.sp, fontWeight = FontWeight.Black, letterSpacing = 1.sp)
            }
            Text(if (liveCount > 0) "● $liveCount LIVE" else "● NO LIVE GAMES", color = if (liveCount > 0) XcRed else XcMuted, fontSize = 11.sp, fontWeight = FontWeight.Black)
        }
        Spacer(Modifier.height(12.dp))
        TextField(value = query, onValueChange = { query = it }, singleLine = true, placeholder = { Text("Search teams, leagues, UFC, networks…", color = XcMuted, fontSize = 12.sp) }, colors = TextFieldDefaults.colors(focusedContainerColor = Color(0xFF080D14), unfocusedContainerColor = Color(0xFF080D14), focusedTextColor = Color.White, unfocusedTextColor = Color.White, focusedIndicatorColor = XcRed, unfocusedIndicatorColor = Color.Transparent), modifier = Modifier.fillMaxWidth().height(56.dp), shape = RoundedCornerShape(13.dp))
        Spacer(Modifier.height(12.dp))
        XcSection("MY SPORTS", "PRESS TO PIN")
        Spacer(Modifier.height(8.dp))
        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            items(filtered) { sport ->
                val favorite = favorites.contains(sport)
                Box(Modifier.clip(RoundedCornerShape(12.dp)).background(if (favorite) Color(0x332E8BFF) else XcPanel2).border(1.dp, if (favorite) Color(0xFF2E8BFF) else Color.Transparent, RoundedCornerShape(12.dp)).clickable { favorites = if (favorite) favorites - sport else favorites + sport }.padding(horizontal = 14.dp, vertical = 10.dp)) {
                    Text(if (favorite) "★ $sport" else sport, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black)
                }
            }
        }
        Spacer(Modifier.height(14.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            XcTvPanel("SPORTS NEWS", "LATEST HEADLINES", Color(0xFFFF6D00), Modifier.weight(1f))
            XcTvPanel("NETWORKS", "SOURCE HEALTH", Color(0xFF63E6BE), Modifier.weight(1f))
            XcTvPanel("FAVORITES", if (favorites.isEmpty()) "PIN YOUR SPORTS" else favorites.joinToString(" • "), Color(0xFF2E8BFF), Modifier.weight(1f))
        }
        Spacer(Modifier.height(10.dp))
        Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(Color(0xFF151A22)).clickable { onConnect() }.padding(12.dp)) {
            Text("SOURCE HEALTH  •  ESPN / ACC / SEC / NFL NETWORK / FS1 / CBS SPORTS  •  OPEN SOURCE SETTINGS →", color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Black)
        }
    }
}

@Composable private fun XcSection(title: String, subtitle: String) { Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) { Box(Modifier.size(7.dp).background(XcRed, RoundedCornerShape(50))); Spacer(Modifier.width(8.dp)); Text(title, color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.Black, letterSpacing = 1.1.sp); Spacer(Modifier.width(7.dp)); Text(subtitle, color = XcMuted, fontSize = 7.sp, fontWeight = FontWeight.Black, letterSpacing = .7.sp) } }
@Composable private fun XcInfoCard(label: String, title: String, detail: String, ready: Boolean, onConnect: () -> Unit) { Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(15.dp)).background(XcPanel).border(1.dp, XcRed.copy(alpha = .15f), RoundedCornerShape(15.dp)).clickable { if (!ready) onConnect() }.padding(13.dp), verticalAlignment = Alignment.CenterVertically) { Box(Modifier.clip(RoundedCornerShape(9.dp)).background(XcRed).padding(horizontal = 8.dp, vertical = 7.dp)) { Text(label, color = Color.White, fontSize = 8.sp, fontWeight = FontWeight.Black) }; Spacer(Modifier.width(11.dp)); Column(Modifier.weight(1f)) { Text(title, color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.Black); Text(detail, color = XcMuted, fontSize = 8.sp, maxLines = 1, overflow = TextOverflow.Ellipsis) }; Text(if (ready) "READY" else "CONNECT", color = if (ready) Color(0xFF63E6BE) else XcRed, fontSize = 8.sp, fontWeight = FontWeight.Black) } }
@Composable private fun XcTvPanel(title: String, value: String, accent: Color, modifier: Modifier) { Column(modifier.clip(RoundedCornerShape(13.dp)).background(XcPanel).border(1.dp, accent.copy(alpha = .35f), RoundedCornerShape(13.dp)).padding(13.dp)) { Text(title, color = accent, fontSize = 9.sp, fontWeight = FontWeight.Black); Spacer(Modifier.height(6.dp)); Text(value, color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.Black, maxLines = 2, overflow = TextOverflow.Ellipsis) } }
