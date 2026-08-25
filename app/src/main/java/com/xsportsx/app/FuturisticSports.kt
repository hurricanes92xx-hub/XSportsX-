package com.xsportsx.app

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val XRed = Color(0xFFFF1744)
private val XOrange = Color(0xFFFF6D00)
private val Void = Color(0xFF05060A)
private val Panel = Color(0xFF0D1119)
private val Panel2 = Color(0xFF141A24)
private val Muted = Color(0xFF727B8B)

data class XNetwork(val name: String, val type: String, val icon: String)
private val xNetworks = listOf(
    XNetwork("ESPN", "SPORTS", "ESPN"), XNetwork("ESPN2", "SPORTS", "ESPN2"),
    XNetwork("ESPNU", "COLLEGE", "ESPNU"), XNetwork("NFL Network", "NFL", "NFL"),
    XNetwork("FS1", "SPORTS", "FS1"), XNetwork("CBS Sports", "SPORTS", "CBS"),
    XNetwork("SEC Network", "COLLEGE", "SEC"), XNetwork("ACC Network", "COLLEGE", "ACC"),
    XNetwork("Big Ten Network", "COLLEGE", "B1G"), XNetwork("Big 12", "COLLEGE", "B12")
)

private data class SportVisual(val name: String, val icon: String)
private val sports = listOf(
    SportVisual("NFL", "NFL"), SportVisual("NBA", "NBA"), SportVisual("NCAA", "NCAA"),
    SportVisual("MLB", "MLB"), SportVisual("NHL", "NHL"), SportVisual("UFC", "UFC"),
    SportVisual("BOXING", "BOX"), SportVisual("SOCCER", "FC")
)

@Composable
private fun SportGlyph(label: String, size: androidx.compose.ui.unit.Dp = 28.dp) {
    Box(
        Modifier.size(size).clip(RoundedCornerShape(size / 3)).background(
            Brush.linearGradient(listOf(Color(0xFF202A38), Color(0xFF10141D)))
        ),
        contentAlignment = Alignment.Center
    ) {
        Text(label, color = Color.White, fontSize = if (label.length > 3) 7.sp else 8.sp, fontWeight = FontWeight.Black, letterSpacing = .2.sp)
    }
}

@Composable
fun FuturisticHome(onConnect: () -> Unit = {}, onNetwork: (XNetwork) -> Unit = {}) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val sourceConfigured = remember { SourceStore(context).load().isConfigured() }
    var selectedSection by remember { mutableStateOf("HOME") }
    val pulse = rememberInfiniteTransition(label = "mobilePulse")
    val alpha by pulse.animateFloat(.35f, 1f, infiniteRepeatable(tween(750), RepeatMode.Reverse), label = "pulse")
    val crackAlpha by pulse.animateFloat(.18f, .50f, infiniteRepeatable(tween(1400), RepeatMode.Reverse), label = "cracks")

    MaterialTheme(colorScheme = darkColorScheme(primary = XRed, secondary = XOrange, background = Void, surface = Panel)) {
        Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color(0xFF080A10), Void)))) {
            GlowingCracks(Modifier.fillMaxSize(), crackAlpha)
            Column(Modifier.fillMaxSize()) {
                Column(Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState()).padding(start = 20.dp, end = 20.dp, top = 18.dp, bottom = 92.dp)) {
                    MobileHeader(sourceConfigured, alpha, onConnect)
                    Spacer(Modifier.height(16.dp))
                    when (selectedSection) {
                        "LIVE" -> MobileLiveCenter(sourceConfigured, onConnect, onNetwork)
                        "NETWORKS" -> MobileNetworks(sourceConfigured, onConnect, onNetwork)
                        "FAVORITES" -> MobileFavorites(onConnect)
                        else -> MobileHomeContent(sourceConfigured, onConnect, onNetwork)
                    }
                }
                MobileBottomNav(selectedSection) { selectedSection = it }
            }
        }
    }
}

@Composable
private fun MobileHeader(sourceConfigured: Boolean, pulseAlpha: Float, onConnect: () -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.weight(1f)) {
            Text("XSPORTS", color = Color.White, fontSize = 29.sp, fontWeight = FontWeight.Black, letterSpacing = 3.sp)
            Text("NEXT-GEN SPORTS COMMAND", color = Color(0xFF687180), fontSize = 8.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.8.sp)
        }
        Box(Modifier.clip(RoundedCornerShape(18.dp)).background(if (sourceConfigured) Color(0x2219FF72) else Color(0x22FF1744)).clickable { onConnect() }.padding(horizontal = 10.dp, vertical = 7.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(7.dp).alpha(pulseAlpha).clip(RoundedCornerShape(50)).background(if (sourceConfigured) Color(0xFF22FF7A) else XRed))
                Spacer(Modifier.width(6.dp))
                Text(if (sourceConfigured) "SOURCE READY" else "ADD SOURCE", color = if (sourceConfigured) Color(0xFF74FFAA) else Color(0xFFFF7185), fontSize = 8.sp, fontWeight = FontWeight.Black)
            }
        }
    }
}

@Composable
private fun MobileHomeContent(sourceConfigured: Boolean, onConnect: () -> Unit, onNetwork: (XNetwork) -> Unit) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(24.dp)).clickable { onConnect() }.background(Brush.horizontalGradient(listOf(Color(0xFF260812), Color(0xFF111827), Color(0xFF251108)))).padding(20.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.clip(RoundedCornerShape(7.dp)).background(XRed).padding(horizontal = 8.dp, vertical = 5.dp)) { Text("LIVE", color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Black) }
                Spacer(Modifier.width(8.dp)); Text("LIVE CENTER", color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Black, letterSpacing = 1.2.sp)
            }
            Spacer(Modifier.height(10.dp)); Text("YOUR GAMES.\nONE COMMAND CENTER.", color = Color.White, fontSize = 25.sp, fontWeight = FontWeight.Black, lineHeight = 28.sp)
            Spacer(Modifier.height(7.dp)); Text(if (sourceConfigured) "Source connected. Browse events and networks." else "Connect your authorized source to unlock live event matching and network streams.", color = Color(0xFF9BA4B2), fontSize = 11.sp, lineHeight = 16.sp)
            Spacer(Modifier.height(12.dp)); Box(Modifier.clip(RoundedCornerShape(10.dp)).background(XRed).padding(horizontal = 13.dp, vertical = 8.dp)) { Text(if (sourceConfigured) "BROWSE LIVE →" else "CONNECT NOW →", color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Black) }
        }
        Text("◈", color = XRed, fontSize = 58.sp, fontWeight = FontWeight.Black)
    }
    Spacer(Modifier.height(20.dp)); MobileSectionLabel("SPORTS", null); Spacer(Modifier.height(8.dp))
    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp), contentPadding = PaddingValues(end = 6.dp)) { items(sports) { sport -> SportPill(sport) { if (!sourceConfigured) onConnect() } } }
    Spacer(Modifier.height(20.dp)); MobileSectionLabel("NETWORKS", "SMART ROW"); Spacer(Modifier.height(8.dp))
    LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(end = 8.dp)) { items(xNetworks.take(6)) { NetworkCard(it, onNetwork) } }
    Spacer(Modifier.height(20.dp)); MobileSectionLabel("COLLEGE NETWORKS", null); Spacer(Modifier.height(8.dp))
    LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(end = 8.dp)) { items(xNetworks.filter { it.type == "COLLEGE" }) { NetworkCard(it, onNetwork) } }
    Spacer(Modifier.height(20.dp)); MobileSectionLabel("UP NEXT", "SPORTS FEED"); Spacer(Modifier.height(8.dp)); UpcomingStrip()
}

@Composable
private fun MobileLiveCenter(sourceConfigured: Boolean, onConnect: () -> Unit, onNetwork: (XNetwork) -> Unit) {
    MobileSectionLabel("LIVE CENTER", if (sourceConfigured) "SOURCE READY" else "CONNECT SOURCE"); Spacer(Modifier.height(10.dp))
    if (!sourceConfigured) ActionPanel("CONNECT YOUR SOURCE", "Connect Xtream/M3U, then XSportsX can match your live events and networks.", "CONNECT SOURCE →", onConnect)
    else { ActionPanel("LIVE EVENT MATCHING", "Your source is connected. Choose a network to browse matched streams.", "REFRESH LIVE →", onConnect); Spacer(Modifier.height(18.dp)); LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) { items(xNetworks.take(8)) { NetworkCard(it, onNetwork) } } }
}

@Composable
private fun MobileNetworks(sourceConfigured: Boolean, onConnect: () -> Unit, onNetwork: (XNetwork) -> Unit) {
    MobileSectionLabel("NETWORKS", "SOURCE MATCH"); Spacer(Modifier.height(10.dp))
    if (!sourceConfigured) { ActionPanel("NETWORKS ARE READY", "Connect your authorized source to turn these cards into playable source matches.", "ADD SOURCE →", onConnect); Spacer(Modifier.height(16.dp)) }
    LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) { items(xNetworks) { NetworkCard(it, onNetwork) } }
    Spacer(Modifier.height(20.dp)); MobileSectionLabel("COLLEGE NETWORKS", null); Spacer(Modifier.height(10.dp)); LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) { items(xNetworks.filter { it.type == "COLLEGE" }) { NetworkCard(it, onNetwork) } }
}

@Composable private fun MobileFavorites(onConnect: () -> Unit) { MobileSectionLabel("FAVORITES", "YOUR PICKS"); Spacer(Modifier.height(12.dp)); ActionPanel("YOUR FAVORITES LIVE HERE", "Pin teams, networks and events once your source is connected.", "ADD SOURCE →", onConnect) }
@Composable private fun MobileSectionLabel(title: String, eyebrow: String?) { Row(verticalAlignment = Alignment.CenterVertically) { Text(title, color = Color.White, fontSize = 15.sp, fontWeight = FontWeight.Black, letterSpacing = 1.4.sp); eyebrow?.let { Spacer(Modifier.width(8.dp)); Text(it, color = Muted, fontSize = 8.sp, fontWeight = FontWeight.Black, letterSpacing = .8.sp) } } }
@Composable private fun ActionPanel(title: String, body: String, button: String, onClick: () -> Unit) { Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp)).background(Brush.horizontalGradient(listOf(Color(0xFF111722), Color(0xFF171018)))).padding(18.dp)) { Text(title, color = Color.White, fontSize = 17.sp, fontWeight = FontWeight.Black); Spacer(Modifier.height(6.dp)); Text(body, color = Color(0xFF8F98A7), fontSize = 11.sp, lineHeight = 16.sp); Spacer(Modifier.height(13.dp)); Box(Modifier.clip(RoundedCornerShape(10.dp)).background(XRed).clickable { onClick() }.padding(horizontal = 14.dp, vertical = 9.dp)) { Text(button, color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Black) } } }

@Composable
private fun SportPill(sport: SportVisual, onClick: () -> Unit) {
    Row(Modifier.clip(RoundedCornerShape(15.dp)).background(Panel2).clickable { onClick() }.padding(horizontal = 13.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
        SportGlyph(sport.icon, 26.dp); Spacer(Modifier.width(7.dp)); Text(sport.name, color = Color(0xFFDCE1E9), fontSize = 10.sp, fontWeight = FontWeight.Black)
    }
}

@Composable
private fun NetworkCard(network: XNetwork, onClick: (XNetwork) -> Unit) {
    Column(Modifier.width(118.dp).height(136.dp).clip(RoundedCornerShape(18.dp)).background(Panel).clickable { onClick(network) }.padding(13.dp)) {
        SportGlyph(network.icon, 40.dp)
        Spacer(Modifier.height(9.dp)); Text(network.name, color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
        Spacer(Modifier.height(3.dp)); Text("SOURCE MATCH", color = Color(0xFF697382), fontSize = 7.sp, fontWeight = FontWeight.Black, letterSpacing = .7.sp)
    }
}

@Composable
private fun UpcomingStrip() {
    val items = listOf("NFL", "NBA", "UFC", "MLB")
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
        items.take(3).forEach { sport ->
            Box(Modifier.weight(1f).clip(RoundedCornerShape(14.dp)).background(Panel).padding(vertical = 13.dp), contentAlignment = Alignment.Center) {
                Row(verticalAlignment = Alignment.CenterVertically) { SportGlyph(sport, 22.dp); Spacer(Modifier.width(5.dp)); Text(sport, color = Color(0xFFDCE1E9), fontSize = 9.sp, fontWeight = FontWeight.Black) }
            }
        }
    }
}

@Composable
private fun MobileBottomNav(selected: String, onSelect: (String) -> Unit) {
    Row(Modifier.fillMaxWidth().height(70.dp).background(Color(0xF2090B10)).padding(horizontal = 10.dp, vertical = 7.dp), horizontalArrangement = Arrangement.SpaceEvenly, verticalAlignment = Alignment.CenterVertically) {
        MobileNavItem("⌂", "HOME", selected, onSelect); MobileNavItem("●", "LIVE", selected, onSelect); MobileNavItem("▦", "NETWORKS", selected, onSelect); MobileNavItem("★", "FAVORITES", selected, onSelect)
    }
}

@Composable
private fun MobileNavItem(icon: String, label: String, selected: String, onSelect: (String) -> Unit) {
    val active = selected == label
    Column(Modifier.clip(RoundedCornerShape(13.dp)).background(if (active) Color(0xFF25121A) else Color.Transparent).clickable { onSelect(label) }.padding(horizontal = 13.dp, vertical = 5.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(icon, color = if (active) XRed else Color(0xFF7A8290), fontSize = 18.sp, fontWeight = FontWeight.Black)
        Text(label, color = if (active) Color.White else Color(0xFF7A8290), fontSize = 7.sp, fontWeight = FontWeight.Black, letterSpacing = .5.sp)
    }
}

@Composable
private fun GlowingCracks(modifier: Modifier, intensity: Float) {
    Canvas(modifier) {
        val w = size.width; val h = size.height
        val lines = listOf(
            listOf(.00f to .18f, .12f to .23f, .16f to .31f, .30f to .35f),
            listOf(1.00f to .23f, .86f to .29f, .82f to .38f, .68f to .43f),
            listOf(.04f to .73f, .16f to .68f, .22f to .58f, .34f to .55f),
            listOf(.96f to .69f, .84f to .63f, .78f to .54f, .66f to .49f),
            listOf(.40f to .00f, .45f to .10f, .52f to .17f, .59f to .25f)
        )
        lines.forEach { points ->
            for (i in 0 until points.lastIndex) {
                val a = points[i]; val b = points[i + 1]
                drawLine(XRed.copy(alpha = intensity * .10f), androidx.compose.ui.geometry.Offset(a.first * w, a.second * h), androidx.compose.ui.geometry.Offset(b.first * w, b.second * h), strokeWidth = 11f)
                drawLine(XRed.copy(alpha = intensity * .22f), androidx.compose.ui.geometry.Offset(a.first * w, a.second * h), androidx.compose.ui.geometry.Offset(b.first * w, b.second * h), strokeWidth = 4f)
                drawLine(XRed.copy(alpha = intensity), androidx.compose.ui.geometry.Offset(a.first * w, a.second * h), androidx.compose.ui.geometry.Offset(b.first * w, b.second * h), strokeWidth = 1.3f)
            }
        }
    }
}
