from pathlib import Path

# Mobile network cards
p = Path('app/src/main/java/com/xsportsx/app/FuturisticSports.kt')
s = p.read_text()
start = s.index('@Composable\nprivate fun NetworkCard(')
end = s.index('\n\n@Composable\nprivate fun UpcomingStrip()', start)
replacement = '''@Composable
private fun NetworkCard(network: XNetwork, onClick: (XNetwork) -> Unit) {
    Column(Modifier.width(128.dp).height(142.dp).clip(RoundedCornerShape(20.dp)).background(Panel).clickable { onClick(network) }.padding(13.dp)) {
        Box(Modifier.fillMaxWidth().height(50.dp).clip(RoundedCornerShape(13.dp)).background(Brush.linearGradient(listOf(Color(0xFF182231), Color(0xFF0B1018)))), contentAlignment = Alignment.Center) {
            NetworkBrandMark(network.name)
        }
        Spacer(Modifier.height(9.dp))
        Text(network.name, color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
        Spacer(Modifier.height(3.dp))
        Text("SOURCE MATCH", color = Color(0xFF697382), fontSize = 7.sp, fontWeight = FontWeight.Black, letterSpacing = .7.sp)
    }
}

@Composable
private fun NetworkBrandMark(name: String) {
    when (name.uppercase()) {
        "ESPN" -> BrandPill("ESPN", XRed)
        "ESPN2" -> BrandPill("ESPN 2", XRed)
        "ESPNU" -> BrandPill("ESPNU", XRed)
        "NFL NETWORK" -> BrandPill("NFL", Color.White, Color(0xFF14233A))
        "FS1" -> BrandPill("FS1", Color.White, Color(0xFF173A6A))
        "CBS SPORTS" -> BrandPill("CBS SPORTS", Color.White, Color(0xFF1267A5))
        "SEC NETWORK" -> BrandPill("SEC", Color.White, Color(0xFF193C69))
        "ACC NETWORK" -> BrandPill("ACC", Color.White, Color(0xFF1C5C9B))
        "BIG TEN NETWORK" -> BrandPill("B1G", Color.White, Color(0xFF26374A))
        "BIG 12" -> BrandPill("BIG 12", Color.White, Color(0xFF6B1F2A))
        else -> BrandPill(name.take(5).uppercase(), Color.White)
    }
}

@Composable
private fun BrandPill(text: String, foreground: Color, background: Color = Color(0xFF202A38)) {
    Box(Modifier.fillMaxWidth().padding(horizontal = 9.dp).clip(RoundedCornerShape(10.dp)).background(background).padding(horizontal = 8.dp, vertical = 9.dp), contentAlignment = Alignment.Center) {
        Text(text, color = foreground, fontSize = if (text.length > 7) 8.sp else 14.sp, fontWeight = FontWeight.Black, letterSpacing = .4.sp, maxLines = 1)
    }
}
'''
p.write_text(s[:start] + replacement + s[end:])

# TV: replace one-letter/abbreviation-only marks with a stable branded logo treatment.
tv = Path('app/src/main/java/com/xsportsx/app/TvHome.kt')
ts = tv.read_text()
old = '''@Composable private fun TvSportMark(name: String, size: androidx.compose.ui.unit.Dp, focused: Boolean) { Box(Modifier.size(size).clip(RoundedCornerShape(size / 4)).background(if (focused) Color(0xFF241018) else TvPanel2).border(1.dp, if (focused) TvRed else Color(0xFF1B2532), RoundedCornerShape(size / 4)), contentAlignment = Alignment.Center) { Text(teamMark(name), color = if (focused) TvRed else Color.White, fontSize = if (name.length > 5) 7.sp else 9.sp, fontWeight = FontWeight.Black, textAlign = TextAlign.Center) } }'''
new = '''@Composable private fun TvSportMark(name: String, size: androidx.compose.ui.unit.Dp, focused: Boolean) {
    val key = name.uppercase()
    val (label, fg, bg) = when {
        key == "NFL" -> Triple("NFL", Color.White, Color(0xFF102B52))
        key == "NBA" -> Triple("NBA", Color.White, Color(0xFF8B1736))
        key == "NCAA FB" -> Triple("NCAA", Color.White, Color(0xFF6A1515))
        key == "NCAA BB" -> Triple("NCAA", Color.White, Color(0xFF173B67))
        key == "MLB" -> Triple("MLB", Color.White, Color(0xFF173C73))
        key == "NHL" -> Triple("NHL", Color.White, Color(0xFF202A38))
        key == "UFC" -> Triple("UFC", Color.White, Color(0xFF7A0F22))
        key == "BOXING" || key == "BOX" -> Triple("BOX", Color.White, Color(0xFF3A1B10))
        else -> Triple(key.take(5), Color.White, Color(0xFF202A38))
    }
    Box(Modifier.size(size).clip(RoundedCornerShape(size / 4)).background(if (focused) Color(0xFF241018) else bg).border(1.dp, if (focused) TvRed else Color(0xFF273445), RoundedCornerShape(size / 4)), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(label, color = if (focused) TvRed else fg, fontSize = if (label.length > 4) (size.value * .17f).sp else (size.value * .23f).sp, fontWeight = FontWeight.Black, letterSpacing = .3.sp)
            if (size.value >= 40f) Text(when (key) { "NFL" -> "FOOTBALL"; "NBA" -> "BASKETBALL"; "MLB" -> "BASEBALL"; "NHL" -> "HOCKEY"; "UFC" -> "FIGHT"; "BOXING" -> "COMBAT"; else -> "SPORTS" }, color = Color.White.copy(alpha = .62f), fontSize = 5.sp, fontWeight = FontWeight.Bold, letterSpacing = .6.sp)
        }
    }
}'''
if old in ts:
    ts = ts.replace(old, new, 1)
else:
    print('TvSportMark already patched; skipping')
old_card = '''@Composable private fun TvNetworkCard(network: TvNetwork, onClick: () -> Unit) { var focused by remember { mutableStateOf(false) }; Column(Modifier.width(108.dp).height(72.dp).clip(RoundedCornerShape(11.dp)).background(TvPanel).border(1.5.dp, TvBlue.copy(alpha = if (focused) 1f else .16f), RoundedCornerShape(11.dp)).onFocusChanged { focused = it.isFocused }.focusable().clickable { onClick() }, horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) { TvSportMark(network.mark, 30.dp, focused); Text(network.name, color = TvMuted, fontSize = 7.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis) } }'''
new_card = '''@Composable private fun TvNetworkCard(network: TvNetwork, onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    Column(Modifier.width(108.dp).height(86.dp).clip(RoundedCornerShape(11.dp)).background(TvPanel).border(1.5.dp, TvBlue.copy(alpha = if (focused) 1f else .16f), RoundedCornerShape(11.dp)).onFocusChanged { focused = it.isFocused }.focusable().clickable { onClick() }, horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        TvNetworkMark(network.name, network.mark, 42.dp, focused)
        Spacer(Modifier.height(5.dp))
        Text(network.name, color = Color.White, fontSize = 7.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

@Composable private fun TvNetworkMark(name: String, mark: String, size: androidx.compose.ui.unit.Dp, focused: Boolean) {
    val key = name.uppercase()
    val (label, bg, fg) = when {
        key == "ESPN" -> Triple("ESPN", Color(0xFF181818), Color(0xFFFF303F))
        key == "ESPN2" -> Triple("ESPN2", Color(0xFF181818), Color(0xFFFF303F))
        key == "ESPNU" -> Triple("ESPNU", Color(0xFF181818), Color(0xFFFF303F))
        key == "NFL NETWORK" -> Triple("NFL", Color(0xFF102B52), Color.White)
        key == "FS1" -> Triple("FS1", Color(0xFF173A6A), Color.White)
        key == "CBS SPORTS" -> Triple("CBS", Color(0xFF123C63), Color.White)
        key == "SEC NETWORK" -> Triple("SEC", Color(0xFF1B3158), Color.White)
        key == "ACC NETWORK" -> Triple("ACC", Color(0xFF15548B), Color.White)
        key == "BIG TEN NETWORK" -> Triple("B1G", Color(0xFF24374D), Color.White)
        key == "ESPN+" -> Triple("ESPN+", Color(0xFF181818), Color(0xFFFF303F))
        else -> Triple(mark, Color(0xFF202A38), Color.White)
    }
    Box(Modifier.size(size).clip(RoundedCornerShape(size / 4)).background(if (focused) Color(0xFF241018) else bg).border(1.dp, if (focused) TvRed else Color(0xFF273445), RoundedCornerShape(size / 4)), contentAlignment = Alignment.Center) {
        Text(label, color = if (focused) TvRed else fg, fontSize = if (label.length > 4) 8.sp else 11.sp, fontWeight = FontWeight.Black, letterSpacing = .25.sp, textAlign = TextAlign.Center)
    }
}'''
if old_card in ts:
    ts = ts.replace(old_card, new_card, 1)
else:
    print('TvNetworkCard already patched; skipping')
tv.write_text(ts)

# Mobile crack treatment: thicker outer glow, brighter core.
mobile = Path('app/src/main/java/com/xsportsx/app/FuturisticSports.kt')
ms = mobile.read_text()
ms = ms.replace('strokeWidth = 11f)', 'strokeWidth = 20f)', 1)
ms = ms.replace('strokeWidth = 4f)', 'strokeWidth = 7f)', 1)
ms = ms.replace('strokeWidth = 1.3f)', 'strokeWidth = 2.1f)', 1)
mobile.write_text(ms)

# TV gets the same XSportsX crack language, tuned for a 10-foot display.
tv = Path('app/src/main/java/com/xsportsx/app/TvHome.kt')
ts = tv.read_text()
if 'import androidx.compose.foundation.Canvas' not in ts:
    ts = ts.replace('import androidx.compose.foundation.background\n', 'import androidx.compose.foundation.Canvas\nimport androidx.compose.foundation.background\n', 1)
if 'private fun TvGlowingCracks(' not in ts:
    ts += '''\n\n@Composable\nprivate fun TvGlowingCracks(modifier: Modifier) {\n    Canvas(modifier) {\n        val w = size.width\n        val h = size.height\n        val lines = listOf(\n            listOf(.00f to .20f, .11f to .25f, .16f to .34f, .29f to .38f),\n            listOf(1.00f to .17f, .88f to .24f, .83f to .34f, .69f to .40f),\n            listOf(.03f to .77f, .16f to .72f, .23f to .61f, .37f to .57f),\n            listOf(.97f to .73f, .85f to .67f, .79f to .56f, .64f to .51f),\n            listOf(.43f to .00f, .47f to .10f, .53f to .18f, .60f to .27f)\n        )\n        lines.forEach { points ->\n            for (i in 0 until points.lastIndex) {\n                val a = points[i]\n                val b = points[i + 1]\n                val start = androidx.compose.ui.geometry.Offset(a.first * w, a.second * h)\n                val end = androidx.compose.ui.geometry.Offset(b.first * w, b.second * h)\n                drawLine(TvRed.copy(alpha = .10f), start, end, strokeWidth = 24f)\n                drawLine(TvRed.copy(alpha = .20f), start, end, strokeWidth = 10f)\n                drawLine(TvRed.copy(alpha = .72f), start, end, strokeWidth = 3f)\n            }\n        }\n    }\n}\n'''
# Put cracks behind the TV content but above the background.
needle = 'Box(Modifier.fillMaxSize().background(TvBg)) {\n        Row(Modifier.fillMaxSize()) {'
replacement = 'Box(Modifier.fillMaxSize().background(TvBg)) {\n        TvGlowingCracks(Modifier.fillMaxSize())\n        Row(Modifier.fillMaxSize()) {'
if needle in ts:
    ts = ts.replace(needle, replacement, 1)
ts = ts

tv.write_text(ts)

# Bump the signed APK version so installed 1.6.3 builds can receive this UI fix in-app.
gradle = Path('app/build.gradle.kts')
gs = gradle.read_text()
gs = gs.replace('versionCode = 14', 'versionCode = 15', 1)
gs = gs.replace('versionName = "1.6.3"', 'versionName = "1.6.4"', 1)
gradle.write_text(gs)
