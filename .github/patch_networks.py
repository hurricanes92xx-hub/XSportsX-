from pathlib import Path
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
print('patched network cards')
