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
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil3.compose.AsyncImage

private val XRed = Color(0xFFFF102F)
private val XOrange = Color(0xFFFF6D00)
private val Void = Color(0xFF05060A)
private val Panel = Color(0xFF0D1119)
private val Panel2 = Color(0xFF141A24)
private val Muted = Color(0xFF727B8B)

private const val WIKI_LOGO = "https://commons.wikimedia.org/wiki/Special:FilePath/"

data class XNetwork(val name: String, val type: String, val icon: String, val logoUrl: String = "")
private val xNetworks = listOf(
    XNetwork("ESPN", "SPORTS", "ESPN", "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2f/ESPN_wordmark.svg/960px-ESPN_wordmark.svg.png"),
    XNetwork("ESPN2", "SPORTS", "ESPN2", "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bf/ESPN2_logo.svg/960px-ESPN2_logo.svg.png"),
    XNetwork("ESPNU", "SPORTS", "ESPNU", "https://commons.wikimedia.org/wiki/Special:FilePath/ESPN_U_logo.svg?width=256"),
    XNetwork("NFL Network", "SPORTS", "NFL", "https://static.cdnlogo.com/logos/n/50/nfl-network.svg"),
    XNetwork("FS1", "SPORTS", "FS1", "https://commons.wikimedia.org/wiki/Special:FilePath/2015_Fox_Sports_1_logo.svg?width=256"),
    XNetwork("CBS Sports", "SPORTS", "CBS", "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/CBS_Sports_%282021%29.svg/960px-CBS_Sports_%282021%29.svg.png"),
    XNetwork("SEC Network", "SPORTS", "SEC", "https://commons.wikimedia.org/wiki/Special:FilePath/SEC_Network_%282024%29.svg?width=256"),
    XNetwork("ACC Network", "SPORTS", "ACC", "https://commons.wikimedia.org/wiki/Special:FilePath/ACC_Network_ESPN_logo.svg?width=256"),
    XNetwork("Big Ten Network", "SPORTS", "B1G", "https://commons.wikimedia.org/wiki/Special:FilePath/Big_Ten_Network_Logo.svg?width=256"),
    XNetwork("ESPN+", "SPORTS", "ESPN+", "https://commons.wikimedia.org/wiki/Special:FilePath/ESPN%2B_logo.svg?width=256"),
    XNetwork("Pac-12 Network", "SPORTS", "PAC12", "https://commons.wikimedia.org/wiki/Special:FilePath/Pac-12_Network_logo.svg?width=256"),
    XNetwork("Red Bull TV", "ACTION", "RED BULL", "https://img.logokit.com/redbull.tv"),
    XNetwork("Monster Jam", "MOTORSPORT", "MJ", "https://commons.wikimedia.org/wiki/Special:FilePath/Monster_Jam_logo.svg?width=256"),
    XNetwork("RugbyPass TV", "RUGBY", "RUGBY", "https://commons.wikimedia.org/wiki/Special:FilePath/Logo_WXV.svg?width=256")
)

private data class SportVisual(val name: String, val icon: String, val logoUrl: String)
private val sports = listOf(
    SportVisual("NFL", "NFL", "https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png"),
    SportVisual("NBA", "NBA", "https://a.espncdn.com/i/teamlogos/leagues/500/nba.png"),
    SportVisual("NCAA FB", "NCAA", "https://a.espncdn.com/i/teamlogos/leagues/500/ncaaf.png"),
    SportVisual("NCAA BB", "NCAA", "https://a.espncdn.com/i/teamlogos/leagues/500/ncaab.png"),
    SportVisual("MLB", "MLB", "https://a.espncdn.com/i/teamlogos/leagues/500/mlb.png"),
    SportVisual("NHL", "NHL", "https://a.espncdn.com/i/teamlogos/leagues/500/nhl.png"),
    SportVisual("UFC", "UFC", "https://commons.wikimedia.org/wiki/Special:FilePath/UFC_Logo.svg?width=256"),
    SportVisual("BOXING", "BOX", "https://commons.wikimedia.org/wiki/Special:FilePath/World_Boxing_logo_2023.svg?width=256"),
    SportVisual("RUGBY", "RUGBY", "https://commons.wikimedia.org/wiki/Special:FilePath/Logo_WXV.svg?width=256"),
    SportVisual("VOLLEYBALL", "VB", "https://commons.wikimedia.org/wiki/Special:FilePath/F%C3%A9d%C3%A9ration_Internationale_de_Volleyball_logo.svg?width=256"),
    SportVisual("LACROSSE", "LAX", "https://commons.wikimedia.org/wiki/Special:FilePath/World_Lacrosse_logo.png?width=256"),
    SportVisual("WRESTLING", "WWE", "https://commons.wikimedia.org/wiki/Special:FilePath/WWE_Official_Logo.svg?width=256"),
    SportVisual("MOTOGP", "GP", "https://commons.wikimedia.org/wiki/Special:FilePath/MotoGP_logo_%282024%29.svg?width=256"),
    SportVisual("WRC", "WRC", "https://commons.wikimedia.org/wiki/Special:FilePath/WRC_logo.svg?width=256"),
    SportVisual("WEC", "WEC", "https://commons.wikimedia.org/wiki/Special:FilePath/WEC_Logo.svg?width=256"),
    SportVisual("IMSA", "IMSA", "https://commons.wikimedia.org/wiki/Special:FilePath/IMSA_SportsCar_Championship_logo.svg?width=256"),
    SportVisual("FORMULA E", "FE", "https://commons.wikimedia.org/wiki/Special:FilePath/Formula-e-logo-championship_2023.svg?width=256"),
    SportVisual("MXGP", "MX", "https://commons.wikimedia.org/wiki/Special:FilePath/Logo_MXGP.svg?width=256"),
    SportVisual("MONSTER JAM", "MJ", "https://commons.wikimedia.org/wiki/Special:FilePath/Monster_Jam_logo.svg?width=256"),
    SportVisual("ESPORTS", "ESPORTS", ""),
    SportVisual("ACTION SPORTS", "ACTION", "")
)

@Composable private fun SportGlyph(label: String, size: androidx.compose.ui.unit.Dp = 28.dp) { Box(Modifier.size(size).clip(RoundedCornerShape(size / 3)).background(Brush.linearGradient(listOf(Color(0xFF202A38), Color(0xFF10141D)))), contentAlignment = Alignment.Center) { Text(label, color = Color.White, fontSize = if (label.length > 3) 7.sp else 8.sp, fontWeight = FontWeight.Black, letterSpacing = .2.sp, maxLines = 1) } }

@Composable private fun LockedLogo(label:String,name:String=label,size:androidx.compose.ui.unit.Dp=62.dp){
    val k=name.uppercase()
    val bg=when{
        k.contains("ESPN")||k.contains("F1") -> Color(0xFFE50920)
        k.contains("SEC") -> Color(0xFF174A7E)
        k.contains("ACC") -> Color(0xFF0066A1)
        k.contains("B1G") -> Color(0xFF151A20)
        k.contains("NFL") -> Color(0xFF013369)
        k.contains("NBA") -> Color(0xFF17408B)
        k.contains("NASCAR") -> Color(0xFF101318)
        k.contains("DTM") -> Color(0xFF28384A)
        k.contains("MONSTER") -> Color(0xFF151515)
        k.contains("RUGBY") -> Color(0xFF0B5E45)
        else -> Color(0xFF202A38)
    }
    Box(Modifier.size(size).clip(RoundedCornerShape(size/3)).background(bg),contentAlignment=Alignment.Center){
        Text(label,color=Color.White,fontSize=if(label.length>6)8.sp else 14.sp,fontWeight=FontWeight.Black,maxLines=1,overflow=TextOverflow.Ellipsis)
    }
}

@Composable private fun BadgeImage(url:String,fallback:String,modifier:Modifier=Modifier){
    var failed by remember(url){mutableStateOf(false)}
    val key = fallback.uppercase()
    val wideLogo = key.contains("NFL") || key.contains("MLB") || key.contains("WWE") || key.contains("WRESTLING") || key.contains("NETWORK") || key.contains("ESPN") || key.contains("CBS") || key.contains("FOX") || key.contains("FS1") || key.contains("RUGBY")
    val logoModifier = if (wideLogo) modifier.padding(horizontal = 9.dp, vertical = 7.dp) else modifier.padding(3.dp)
    if(!failed && url.isNotBlank()) {
        AsyncImage(
            model=url,
            contentDescription=fallback,
            modifier=logoModifier,
            contentScale=ContentScale.Fit,
            onError={failed=true}
        )
    } else {
        Box(logoModifier, contentAlignment = Alignment.Center) {
            LockedLogo(fallback,fallback, if (wideLogo) 58.dp else 66.dp)
        }
    }
}

@Composable
fun FuturisticHome(onConnect: () -> Unit = {}, onNetwork: (XNetwork) -> Unit = {}) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val sourceConfigured = remember { SourceStore(context).load().isConfigured() }
    var selectedSection by remember { mutableStateOf("HOME") }
    val pulse = rememberInfiniteTransition(label = "mobilePulse")
    val alpha by pulse.animateFloat(.35f, 1f, infiniteRepeatable(tween(750), RepeatMode.Reverse), label = "pulse")
    val crackAlpha by pulse.animateFloat(.25f, .72f, infiniteRepeatable(tween(900), RepeatMode.Reverse), label = "cracks")
    MaterialTheme(colorScheme = darkColorScheme(primary = XRed, secondary = XOrange, background = Void, surface = Panel)) {
        Box(Modifier.fillMaxSize().background(Brush.radialGradient(listOf(Color(0xFF16080D), Color(0xFF080A10), Void)))) {
            GlowingCracks(Modifier.fillMaxSize(), crackAlpha)
            Column(Modifier.fillMaxSize()) {
                Column(Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState()).padding(start = 20.dp, end = 20.dp, top = 18.dp, bottom = 92.dp)) {
                    MobileHeader(sourceConfigured, alpha, onConnect); Spacer(Modifier.height(16.dp))
                    when (selectedSection) { "LIVE" -> MobileLiveCenter(sourceConfigured, onConnect, onNetwork); "NETWORKS" -> MobileNetworks(sourceConfigured, onConnect, onNetwork); "FAVORITES" -> MobileFavorites(onConnect); else -> MobileHomeContent(sourceConfigured, onConnect, onNetwork) }
                }
                MobileBottomNav(selectedSection) { selectedSection = it }
            }
        }
    }
}

@Composable private fun MobileHeader(sourceConfigured: Boolean, pulseAlpha: Float, onConnect: () -> Unit) { Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) { XtremeLogo(size = 56.dp); Spacer(Modifier.width(10.dp)); Column(Modifier.weight(1f)) { Text("XSPORTS", color = Color.White, fontSize = 29.sp, fontWeight = FontWeight.Black, letterSpacing = 3.sp); Text("NEXT-GEN SPORTS COMMAND", color = Color(0xFF687180), fontSize = 8.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.8.sp) }; Box(Modifier.clip(RoundedCornerShape(18.dp)).background(if (sourceConfigured) Color(0x2219FF72) else Color(0x22FF1744)).clickable { onConnect() }.padding(horizontal = 10.dp, vertical = 7.dp)) { Row(verticalAlignment = Alignment.CenterVertically) { Box(Modifier.size(7.dp).alpha(pulseAlpha).clip(RoundedCornerShape(50)).background(if (sourceConfigured) Color(0xFF22FF7A) else XRed)); Spacer(Modifier.width(6.dp)); Text(if (sourceConfigured) "SOURCE READY" else "ADD SOURCE", color = if (sourceConfigured) Color(0xFF74FFAA) else Color(0xFFFF7185), fontSize = 8.sp, fontWeight = FontWeight.Black) } } } }
@Composable private fun MobileHomeContent(sourceConfigured: Boolean, onConnect: () -> Unit, onNetwork: (XNetwork) -> Unit) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(24.dp)).clickable { onConnect() }.background(Brush.horizontalGradient(listOf(Color(0xFF3A0812), Color(0xFF111827), Color(0xFF30100A)))).padding(20.dp), verticalAlignment = Alignment.CenterVertically) { Column(Modifier.weight(1f)) { Row(verticalAlignment = Alignment.CenterVertically) { Box(Modifier.clip(RoundedCornerShape(7.dp)).background(XRed).padding(horizontal = 8.dp, vertical = 5.dp)) { Text("LIVE", color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Black) }; Spacer(Modifier.width(8.dp)); Text("LIVE CENTER", color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Black, letterSpacing = 1.2.sp) }; Spacer(Modifier.height(10.dp)); Text("YOUR GAMES.\nONE COMMAND CENTER.", color = Color.White, fontSize = 25.sp, fontWeight = FontWeight.Black, lineHeight = 28.sp); Spacer(Modifier.height(7.dp)); Text(if (sourceConfigured) "Source connected. Browse events and networks." else "Connect your authorized source to unlock live event matching and network streams.", color = Color(0xFF9BA4B2), fontSize = 11.sp, lineHeight = 16.sp); Spacer(Modifier.height(12.dp)); Box(Modifier.clip(RoundedCornerShape(10.dp)).background(XRed).padding(horizontal = 13.dp, vertical = 8.dp)) { Text(if (sourceConfigured) "BROWSE LIVE →" else "CONNECT NOW →", color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Black) } }; Text("◈", color = XRed, fontSize = 58.sp, fontWeight = FontWeight.Black) }
    Spacer(Modifier.height(20.dp)); MobileSectionLabel("TOP SPORTS", null); Spacer(Modifier.height(8.dp)); LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(end = 8.dp)) { items(sports, key = { it.name }) { sport -> SportBadgeCard(sport) { onConnect() } } }
    Spacer(Modifier.height(20.dp)); MobileSectionLabel("NETWORKS", null); Spacer(Modifier.height(8.dp)); LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(end = 8.dp)) { items(xNetworks, key = { it.name }) { NetworkCard(it, onNetwork) } }
    Spacer(Modifier.height(20.dp)); MobileSectionLabel("UP NEXT", "SPORTS FEED"); Spacer(Modifier.height(8.dp)); UpcomingStrip()
}
@Composable private fun MobileLiveCenter(sourceConfigured: Boolean, onConnect: () -> Unit, onNetwork: (XNetwork) -> Unit) { MobileSectionLabel("LIVE CENTER", if (sourceConfigured) "SOURCE READY" else "CONNECT SOURCE"); Spacer(Modifier.height(10.dp)); if (!sourceConfigured) ActionPanel("CONNECT YOUR SOURCE", "Connect Xtream/M3U, then XSportsX can match your live events and networks.", "CONNECT SOURCE →", onConnect) else { ActionPanel("LIVE EVENT MATCHING", "Your source is connected. Choose a network to browse matched streams.", "REFRESH LIVE →", onConnect); Spacer(Modifier.height(18.dp)); LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) { items(xNetworks.take(8)) { NetworkCard(it, onNetwork) } } } }
@Composable private fun MobileNetworks(sourceConfigured: Boolean, onConnect: () -> Unit, onNetwork: (XNetwork) -> Unit) { MobileSectionLabel("NETWORKS", "SOURCE MATCH"); Spacer(Modifier.height(10.dp)); if (!sourceConfigured) { ActionPanel("NETWORKS ARE READY", "Connect your authorized source to turn these cards into playable source matches.", "ADD SOURCE →", onConnect); Spacer(Modifier.height(16.dp)) }; LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(end = 8.dp)) { items(xNetworks, key = { it.name }) { NetworkCard(it, onNetwork) } } }
@Composable private fun MobileFavorites(onConnect: () -> Unit) { MobileSectionLabel("FAVORITES", "YOUR PICKS"); Spacer(Modifier.height(12.dp)); ActionPanel("YOUR FAVORITES LIVE HERE", "Pin teams, networks and events once your source is connected.", "ADD SOURCE →", onConnect) }
@Composable private fun MobileSectionLabel(title: String, eyebrow: String?) { Row(verticalAlignment = Alignment.CenterVertically) { Text(title, color = Color.White, fontSize = 15.sp, fontWeight = FontWeight.Black, letterSpacing = 1.4.sp); eyebrow?.let { Spacer(Modifier.width(8.dp)); Text(it, color = Muted, fontSize = 8.sp, fontWeight = FontWeight.Black, letterSpacing = .8.sp) } } }
@Composable private fun ActionPanel(title: String, body: String, button: String, onClick: () -> Unit) { Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp)).background(Brush.horizontalGradient(listOf(Color(0xFF111722), Color(0xFF2A0D14)))).padding(18.dp)) { Text(title, color = Color.White, fontSize = 17.sp, fontWeight = FontWeight.Black); Spacer(Modifier.height(6.dp)); Text(body, color = Color(0xFF8F98A7), fontSize = 11.sp, lineHeight = 16.sp); Spacer(Modifier.height(13.dp)); Box(Modifier.clip(RoundedCornerShape(10.dp)).background(XRed).clickable { onClick() }.padding(horizontal = 14.dp, vertical = 9.dp)) { Text(button, color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Black) } } }
@Composable private fun SportPill(sport: SportVisual, onClick: () -> Unit) { Row(Modifier.clip(RoundedCornerShape(15.dp)).background(Panel2).clickable { onClick() }.padding(horizontal = 13.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) { SportGlyph(sport.icon, 26.dp); Spacer(Modifier.width(7.dp)); Text(sport.name, color = Color(0xFFDCE1E9), fontSize = 10.sp, fontWeight = FontWeight.Black, maxLines = 1) } }
@Composable private fun SportBadgeCard(sport: SportVisual, onClick: () -> Unit) { Column(Modifier.width(118.dp).height(142.dp).clip(RoundedCornerShape(18.dp)).background(Panel).clickable { onClick() }.padding(10.dp), horizontalAlignment = Alignment.CenterHorizontally) { Box(Modifier.fillMaxWidth().height(88.dp), contentAlignment = Alignment.Center) { BadgeImage(sport.logoUrl, sport.icon, Modifier.size(72.dp)) }; Spacer(Modifier.height(5.dp)); Text(sport.name, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black, maxLines = 1, overflow = TextOverflow.Ellipsis) } }
@Composable private fun NetworkCard(network:XNetwork,onClick:(XNetwork)->Unit){
    Column(Modifier.width(132.dp).height(124.dp).clip(RoundedCornerShape(18.dp)).background(Panel).clickable{onClick(network)}.padding(10.dp),horizontalAlignment=Alignment.CenterHorizontally){
        Box(Modifier.fillMaxWidth().height(70.dp).clip(RoundedCornerShape(12.dp)).background(Color(0xFF0A0F17)),contentAlignment=Alignment.Center){
            BadgeImage(network.logoUrl,network.name,Modifier.size(58.dp))
        }
        Spacer(Modifier.height(7.dp))
        Text(network.name,color=Color.White,fontSize=10.sp,fontWeight=FontWeight.Bold,maxLines=1,overflow=TextOverflow.Ellipsis)
    }
}
@Composable private fun BrandPill(text: String, foreground: Color, background: Color = Color(0xFF202A38)) { Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(background).padding(horizontal = 8.dp, vertical = 9.dp), contentAlignment = Alignment.Center) { Text(text, color = foreground, fontSize = if (text.length > 7) 8.sp else 14.sp, fontWeight = FontWeight.Black, letterSpacing = .4.sp, maxLines = 1) } }
@Composable private fun UpcomingStrip() { val items = listOf("NFL", "NBA", "UFC", "MLB"); Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) { items.take(3).forEach { sport -> Box(Modifier.weight(1f).clip(RoundedCornerShape(14.dp)).background(Panel).padding(vertical = 13.dp), contentAlignment = Alignment.Center) { Row(verticalAlignment = Alignment.CenterVertically) { SportGlyph(sport, 22.dp); Spacer(Modifier.width(5.dp)); Text(sport, color = Color(0xFFDCE1E9), fontSize = 9.sp, fontWeight = FontWeight.Black) } } } } }
@Composable private fun MobileBottomNav(selected: String, onSelect: (String) -> Unit) { Row(Modifier.fillMaxWidth().height(70.dp).background(Color(0xF2090B10)).padding(horizontal = 10.dp, vertical = 7.dp), horizontalArrangement = Arrangement.SpaceEvenly, verticalAlignment = Alignment.CenterVertically) { MobileNavItem("⌂", "HOME", selected, onSelect); MobileNavItem("●", "LIVE", selected, onSelect); MobileNavItem("▦", "NETWORKS", selected, onSelect); MobileNavItem("★", "FAVORITES", selected, onSelect) } }
@Composable private fun MobileNavItem(icon: String, label: String, selected: String, onSelect: (String) -> Unit) { val active = selected == label; Column(Modifier.clip(RoundedCornerShape(13.dp)).background(if (active) Color(0xFF25121A) else Color.Transparent).clickable { onSelect(label) }.padding(horizontal = 13.dp, vertical = 5.dp), horizontalAlignment = Alignment.CenterHorizontally) { Text(icon, color = if (active) XRed else Color(0xFF7A8290), fontSize = 18.sp, fontWeight = FontWeight.Black); Text(label, color = if (active) Color.White else Color(0xFF7A8290), fontSize = 7.sp, fontWeight = FontWeight.Black, letterSpacing = .5.sp) } }

@Composable
private fun GlowingCracks(modifier: Modifier, intensity: Float) {
    Canvas(modifier) {
        val w = size.width; val h = size.height
        val lines = listOf(listOf(.00f to .14f, .10f to .20f, .14f to .31f, .28f to .37f), listOf(1.00f to .18f, .89f to .24f, .84f to .34f, .69f to .41f), listOf(.02f to .76f, .13f to .70f, .19f to .59f, .35f to .53f), listOf(.98f to .72f, .87f to .65f, .80f to .54f, .64f to .47f), listOf(.38f to .00f, .43f to .11f, .50f to .18f, .58f to .27f), listOf(.62f to 1f, .57f to .89f, .50f to .82f, .42f to .73f), listOf(.08f to .44f, .19f to .47f, .25f to .42f), listOf(.92f to .48f, .81f to .44f, .75f to .39f))
        lines.forEach { points -> for (i in 0 until points.lastIndex) { val a = points[i]; val b = points[i + 1]; drawLine(XRed.copy(alpha = intensity * .10f), androidx.compose.ui.geometry.Offset(a.first*w,a.second*h), androidx.compose.ui.geometry.Offset(b.first*w,b.second*h), strokeWidth = 28f); drawLine(XRed.copy(alpha = intensity * .24f), androidx.compose.ui.geometry.Offset(a.first*w,a.second*h), androidx.compose.ui.geometry.Offset(b.first*w,b.second*h), strokeWidth = 10f); drawLine(XRed.copy(alpha = intensity), androidx.compose.ui.geometry.Offset(a.first*w,a.second*h), androidx.compose.ui.geometry.Offset(b.first*w,b.second*h), strokeWidth = 2.8f); drawLine(Color.White.copy(alpha = intensity*.20f), androidx.compose.ui.geometry.Offset(a.first*w,a.second*h), androidx.compose.ui.geometry.Offset(b.first*w,b.second*h), strokeWidth = 0.8f) } }
        val shards = listOf(floatArrayOf(.05f,.29f,.12f,.34f), floatArrayOf(.15f,.58f,.22f,.51f), floatArrayOf(.86f,.29f,.95f,.25f), floatArrayOf(.78f,.62f,.90f,.68f), floatArrayOf(.33f,.16f,.38f,.08f), floatArrayOf(.67f,.84f,.72f,.94f))
        shards.forEach { q -> drawLine(XRed.copy(alpha=intensity*.8f), androidx.compose.ui.geometry.Offset(q[0]*w,q[1]*h), androidx.compose.ui.geometry.Offset(q[2]*w,q[3]*h), strokeWidth=2.2f) }
    }
}
