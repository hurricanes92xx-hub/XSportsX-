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
if old not in ts:
    raise SystemExit('TvSportMark pattern not found')
ts = ts.replace(old, new, 1)
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
if old_card not in ts:
    raise SystemExit('TvNetworkCard pattern not found')
ts = ts.replace(old_card, new_card, 1)
tv.write_text(ts)
print('patched mobile + TV logo treatments')
