package com.xsportsx.app

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val XRed = Color(0xFFFF1744)
private val XOrange = Color(0xFFFF6D00)
private val Void = Color(0xFF05060A)
private val Panel = Color(0xFF0D1119)
private val Panel2 = Color(0xFF141A24)

data class XNetwork(val name: String, val type: String, val icon: String)
private val xNetworks = listOf(
    XNetwork("ESPN", "SPORTS", "E"), XNetwork("ESPN2", "SPORTS", "E2"),
    XNetwork("ESPNU", "COLLEGE", "EU"), XNetwork("NFL Network", "NFL", "N"),
    XNetwork("FS1", "SPORTS", "F1"), XNetwork("CBS Sports", "SPORTS", "CBS"),
    XNetwork("SEC Network", "COLLEGE", "SEC"), XNetwork("ACC Network", "COLLEGE", "ACC"),
    XNetwork("Big Ten Network", "COLLEGE", "B1G"), XNetwork("Big 12", "COLLEGE", "B12")
)

@Composable
fun FuturisticHome(
    onConnect: () -> Unit = {},
    onNetwork: (XNetwork) -> Unit = {}
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val sourceConfigured = remember { SourceStore(context).load().isConfigured() }
    val pulse = rememberInfiniteTransition(label = "live")
    val alpha by pulse.animateFloat(.35f, 1f, infiniteRepeatable(tween(750), RepeatMode.Reverse), label = "pulse")
    val sports = listOf("NFL", "NBA", "NCAA", "MLB", "NHL", "UFC", "BOXING", "SOCCER")
    MaterialTheme(colorScheme = darkColorScheme(primary = XRed, secondary = XOrange, background = Void, surface = Panel)) {
        Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color(0xFF080A10), Void)))) {
            Column(Modifier.fillMaxSize().padding(horizontal = 28.dp, vertical = 22.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("XSPORTS", color = Color.White, fontSize = 30.sp, fontWeight = FontWeight.Black, letterSpacing = 3.sp)
                        Text("NEXT-GEN SPORTS COMMAND", color = Color(0xFF687180), fontSize = 9.sp, fontWeight = FontWeight.Bold, letterSpacing = 2.sp)
                    }
                    Box(
                        Modifier.clip(RoundedCornerShape(20.dp))
                            .background(if (sourceConfigured) Color(0x2219FF72) else Color(0x22FF1744))
                            .clickable { onConnect() }
                            .padding(horizontal = 12.dp, vertical = 7.dp)
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(Modifier.size(8.dp).alpha(alpha).clip(RoundedCornerShape(50)).background(if (sourceConfigured) Color(0xFF22FF7A) else XRed))
                            Spacer(Modifier.width(7.dp))
                            Text(if (sourceConfigured) "SOURCE READY" else "CONNECT SOURCE", color = if (sourceConfigured) Color(0xFF74FFAA) else Color(0xFFFF7185), fontSize = 9.sp, fontWeight = FontWeight.Black)
                        }
                    }
                }
                Spacer(Modifier.height(18.dp))
                Row(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(26.dp))
                        .clickable { onConnect() }
                        .background(Brush.horizontalGradient(listOf(Color(0xFF260812), Color(0xFF111827), Color(0xFF251108))))
                        .padding(24.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(Modifier.weight(1f)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(Modifier.clip(RoundedCornerShape(7.dp)).background(XRed).padding(horizontal = 9.dp, vertical = 5.dp)) { Text("LIVE", color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black) }
                            Spacer(Modifier.width(9.dp)); Text("LIVE CENTER", color = Color.White, fontWeight = FontWeight.Black, letterSpacing = 1.5.sp)
                        }
                        Spacer(Modifier.height(10.dp))
                        Text("YOUR GAMES.\nONE COMMAND CENTER.", color = Color.White, fontSize = 27.sp, fontWeight = FontWeight.Black, lineHeight = 30.sp)
                        Spacer(Modifier.height(7.dp))
                        Text(if (sourceConfigured) "Source connected. Tap here to manage it or refresh your connection." else "Connect your authorized source to unlock live event matching and network streams.", color = Color(0xFF9BA4B2), fontSize = 12.sp)
                        Spacer(Modifier.height(12.dp))
                        Box(Modifier.clip(RoundedCornerShape(10.dp)).background(XRed).padding(horizontal = 14.dp, vertical = 8.dp)) { Text(if (sourceConfigured) "MANAGE SOURCE" else "CONNECT NOW →", color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black) }
                    }
                    Text("◈", color = XRed, fontSize = 64.sp, fontWeight = FontWeight.Black)
                }
                Spacer(Modifier.height(18.dp))
                Text("SPORTS", color = Color(0xFF707989), fontSize = 10.sp, fontWeight = FontWeight.Black, letterSpacing = 2.sp)
                Spacer(Modifier.height(9.dp))
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(9.dp)) { sports.forEach { SportPill(it) { if (!sourceConfigured) onConnect() } } }
                Spacer(Modifier.height(20.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("NETWORKS", color = Color.White, fontSize = 15.sp, fontWeight = FontWeight.Black, letterSpacing = 1.5.sp)
                    Spacer(Modifier.width(8.dp)); Text("SMART ROW", color = Color(0xFF646D7B), fontSize = 8.sp, fontWeight = FontWeight.Bold)
                }
                Spacer(Modifier.height(9.dp))
                LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(end = 12.dp)) { items(xNetworks.take(6)) { NetworkCard(it, onNetwork) } }
                Spacer(Modifier.height(18.dp))
                Text("COLLEGE NETWORKS", color = Color.White, fontSize = 15.sp, fontWeight = FontWeight.Black, letterSpacing = 1.5.sp)
                Spacer(Modifier.height(9.dp))
                LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(end = 12.dp)) { items(xNetworks.filter { it.type == "COLLEGE" }) { NetworkCard(it, onNetwork) } }
            }
        }
    }
}

@Composable private fun SportPill(name: String, onClick: () -> Unit) {
    Box(Modifier.clip(RoundedCornerShape(15.dp)).background(Panel2).clickable { onClick() }.padding(horizontal = 15.dp, vertical = 11.dp)) { Text(name, color = Color(0xFFDCE1E9), fontSize = 11.sp, fontWeight = FontWeight.Black) }
}

@Composable private fun NetworkCard(network: XNetwork, onClick: (XNetwork) -> Unit) {
    Column(Modifier.width(112.dp).clip(RoundedCornerShape(18.dp)).background(Panel).clickable { onClick(network) }.padding(13.dp)) {
        Box(Modifier.size(38.dp).clip(RoundedCornerShape(12.dp)).background(Brush.linearGradient(listOf(Color(0xFF202A38), Color(0xFF11151E)))), contentAlignment = Alignment.Center) { Text(network.icon, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black) }
        Spacer(Modifier.height(9.dp)); Text(network.name, color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.Bold, maxLines = 1)
        Text("SOURCE MATCH", color = Color(0xFF697382), fontSize = 8.sp, fontWeight = FontWeight.Black, letterSpacing = .7.sp)
    }
}
