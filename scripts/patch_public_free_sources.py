from pathlib import Path
import re

FUT = Path("app/src/main/java/com/xsportsx/app/FuturisticSports.kt")
TV = Path("app/src/main/java/com/xsportsx/app/TvHome.kt")

for path in (FUT, TV):
    if not path.is_file():
        continue
    s = path.read_text(encoding="utf-8")
    replacements = {
        "Connect your authorized source to unlock live event matching and network streams.": "Free public sports streams are available now. Add Xtream/M3U only for your own source.",
        "Connect Xtream/M3U, then XSportsX can match your live events and networks.": "Free public streams work without login. Add Xtream/M3U only for your own source.",
        "Connect your authorized source to turn these cards into playable source matches.": "Free public streams are playable without login. Add a private source for additional channels.",
        "SPORTS NETWORKS": "FREE SPORTS SOURCES",
        "LIVE SOURCES": "NO LOGIN REQUIRED",
        'MobileSectionLabel("NETWORKS", null)': 'MobileSectionLabel("FREE SPORTS SOURCES", "NO LOGIN")',
    }
    for old, new in replacements.items():
        s = s.replace(old, new)
    path.write_text(s, encoding="utf-8")

if not FUT.is_file():
    print("Public free-source UI patch: FuturisticSports.kt not present")
    raise SystemExit(0)

s = FUT.read_text(encoding="utf-8")
old = 'val sourceConfigured = remember { SourceStore(context).load().isConfigured() }'
new = '''val sourceConfigured = remember { SourceStore(context).load().isConfigured() }\n    var publicStreams by remember { mutableStateOf<List<PublicResolvedStream>>(emptyList()) }\n    LaunchedEffect(Unit) {\n        publicStreams = runCatching { PublicSourceResolver().load() }.getOrDefault(emptyList())\n    }\n    val publicAvailable = publicStreams.isNotEmpty()'''
if old in s:
    s = s.replace(old, new, 1)

s = s.replace('MobileHeader(sourceConfigured, alpha, onConnect)', 'MobileHeader(sourceConfigured, publicAvailable, alpha, onConnect)')
s = s.replace('MobileLiveCenter(sourceConfigured, onConnect, onNetwork)', 'MobileLiveCenter(sourceConfigured, publicStreams, onConnect, onNetwork)')
s = s.replace('MobileHomeContent(sourceConfigured, onConnect, onNetwork)', 'MobileHomeContent(sourceConfigured, publicStreams, onConnect, onNetwork)')
s = s.replace('private fun MobileHeader(sourceConfigured: Boolean, pulseAlpha: Float, onConnect: () -> Unit)', 'private fun MobileHeader(sourceConfigured: Boolean, publicAvailable: Boolean, pulseAlpha: Float, onConnect: () -> Unit)')
s = s.replace('if (sourceConfigured) "SOURCE READY" else "ADD SOURCE"', 'if (sourceConfigured) "SOURCE READY" else if (publicAvailable) "FREE LIVE" else "ADD SOURCE"')
s = s.replace('private fun MobileHomeContent(sourceConfigured: Boolean, onConnect: () -> Unit, onNetwork: (XNetwork) -> Unit)', 'private fun MobileHomeContent(sourceConfigured: Boolean, publicStreams: List<PublicResolvedStream>, onConnect: () -> Unit, onNetwork: (XNetwork) -> Unit)')

pattern = re.compile(r'@Composable private fun MobileLiveCenter\(.*?(?=@Composable private fun MobileNetworks)', re.DOTALL)
replacement = '''@Composable private fun MobileLiveCenter(sourceConfigured: Boolean, publicStreams: List<PublicResolvedStream>, onConnect: () -> Unit, onNetwork: (XNetwork) -> Unit) {\n    MobileSectionLabel("LIVE CENTER", if (publicStreams.isNotEmpty()) "FREE • NO LOGIN" else if (sourceConfigured) "SOURCE READY" else "ADD SOURCE")\n    Spacer(Modifier.height(10.dp))\n    if (publicStreams.isNotEmpty()) {\n        Text("PUBLIC SPORTS STREAMS", color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.Black, letterSpacing = 1.1.sp)\n        Spacer(Modifier.height(8.dp))\n        LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(end = 8.dp)) {\n            items(publicStreams.take(24), key = { it.url }) { stream -> PublicStreamCard(stream) }\n        }\n        Spacer(Modifier.height(14.dp))\n        Text("Private Xtream/M3U is optional and only adds your own source.", color = Muted, fontSize = 10.sp)\n    } else if (sourceConfigured) {\n        ActionPanel("LIVE EVENT MATCHING", "Your source is connected. Choose a network to browse matched streams.", "REFRESH LIVE →", onConnect)\n    } else {\n        ActionPanel("PUBLIC SOURCES LOADING", "XSportsX is checking authorized public sports streams. No login is required.", "REFRESH →", onConnect)\n    }\n}\n\n@Composable private fun PublicStreamCard(stream: PublicResolvedStream) {\n    val context = androidx.compose.ui.platform.LocalContext.current\n    Column(Modifier.width(220.dp).clip(RoundedCornerShape(16.dp)).background(Panel2).clickable {\n        runCatching {\n            val intent = android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(stream.url))\n            context.startActivity(intent)\n        }\n    }.padding(14.dp)) {\n        Row(verticalAlignment = Alignment.CenterVertically) {\n            if (stream.iconUrl.isNotBlank()) BadgeImage(stream.iconUrl, "LIVE", Modifier.size(34.dp)) else SportGlyph("LIVE", 34.dp)\n            Spacer(Modifier.width(9.dp))\n            Column(Modifier.weight(1f)) {\n                Text("FREE", color = Color(0xFF74FFAA), fontSize = 8.sp, fontWeight = FontWeight.Black)\n                Text(stream.sourceName, color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)\n            }\n        }\n        Spacer(Modifier.height(9.dp))\n        Text(stream.name, color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.Black, maxLines = 2, overflow = TextOverflow.Ellipsis)\n        Text(stream.group, color = Muted, fontSize = 9.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)\n        Spacer(Modifier.height(8.dp))\n        Text("WATCH →", color = XRed, fontSize = 9.sp, fontWeight = FontWeight.Black)\n    }\n}\n\n'''
s, count = pattern.subn(replacement, s, count=1)
if count != 1:
    raise SystemExit("Could not locate MobileLiveCenter block")

needle = 'Spacer(Modifier.height(20.dp)); MobileSectionLabel("NETWORKS", null);'
insert = 'Spacer(Modifier.height(20.dp)); MobileSectionLabel("FREE SPORTS SOURCES", "NO LOGIN"); Spacer(Modifier.height(8.dp)); LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(end = 8.dp)) { items(publicStreams.take(12), key = { it.url }) { stream -> PublicStreamCard(stream) } }; Spacer(Modifier.height(20.dp)); MobileSectionLabel("NETWORKS", null);'
if needle in s:
    s = s.replace(needle, insert, 1)

FUT.write_text(s, encoding="utf-8")
print("Public free-source UI patch: FuturisticSports.kt (public-first flow wired)")
