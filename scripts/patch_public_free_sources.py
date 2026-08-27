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
new = '''val sourceConfigured = remember { SourceStore(context).load().isConfigured() }
    var publicStreams by remember { mutableStateOf<List<PublicResolvedStream>>(emptyList()) }
    LaunchedEffect(Unit) {
        publicStreams = runCatching { PublicSourceResolver().load() }.getOrDefault(emptyList())
    }
    val publicAvailable = publicStreams.isNotEmpty()'''
if old in s:
    s = s.replace(old, new, 1)

s = s.replace('MobileHeader(sourceConfigured, alpha, onConnect)', 'MobileHeader(sourceConfigured, publicAvailable, alpha, onConnect)')
s = s.replace('MobileLiveCenter(sourceConfigured, onConnect, onNetwork)', 'MobileLiveCenter(sourceConfigured, publicStreams, onConnect, onNetwork)')
s = s.replace('MobileHomeContent(sourceConfigured, onConnect, onNetwork)', 'MobileHomeContent(sourceConfigured, publicStreams, onConnect, onNetwork)')
s = s.replace('private fun MobileHeader(sourceConfigured: Boolean, pulseAlpha: Float, onConnect: () -> Unit)', 'private fun MobileHeader(sourceConfigured: Boolean, publicAvailable: Boolean, pulseAlpha: Float, onConnect: () -> Unit)')
s = s.replace('if (sourceConfigured) "SOURCE READY" else "ADD SOURCE"', 'if (sourceConfigured) "SOURCE READY" else if (publicAvailable) "FREE LIVE" else "ADD SOURCE"')
s = s.replace('private fun MobileHomeContent(sourceConfigured: Boolean, onConnect: () -> Unit, onNetwork: (XNetwork) -> Unit)', 'private fun MobileHomeContent(sourceConfigured: Boolean, publicStreams: List<PublicResolvedStream>, onConnect: () -> Unit, onNetwork: (XNetwork) -> Unit)')

pattern = re.compile(r'@Composable private fun MobileLiveCenter\(.*?(?=@Composable private fun MobileNetworks)', re.DOTALL)
replacement = '''@Composable private fun MobileLiveCenter(sourceConfigured: Boolean, publicStreams: List<PublicResolvedStream>, onConnect: () -> Unit, onNetwork: (XNetwork) -> Unit) {
    MobileSectionLabel("LIVE CENTER", if (publicStreams.isNotEmpty()) "FREE • NO LOGIN" else if (sourceConfigured) "SOURCE READY" else "ADD SOURCE")
    Spacer(Modifier.height(10.dp))
    if (publicStreams.isNotEmpty()) {
        Text("PUBLIC SPORTS STREAMS", color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.Black, letterSpacing = 1.1.sp)
        Spacer(Modifier.height(8.dp))
        LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(end = 8.dp)) {
            items(publicStreams.take(24), key = { it.url }) { stream -> PublicStreamCard(stream) }
        }
        Spacer(Modifier.height(14.dp))
        Text("Private Xtream/M3U is optional and only adds your own source.", color = Muted, fontSize = 10.sp)
    } else if (sourceConfigured) {
        ActionPanel("LIVE EVENT MATCHING", "Your source is connected. Choose a network to browse matched streams.", "REFRESH LIVE →", onConnect)
    } else {
        ActionPanel("PUBLIC SOURCES LOADING", "XSportsX is checking authorized public sports streams. No login is required.", "REFRESH →", onConnect)
    }
}

@Composable private fun PublicStreamCard(stream: PublicResolvedStream) {
    val context = androidx.compose.ui.platform.LocalContext.current
    Column(Modifier.width(220.dp).clip(RoundedCornerShape(16.dp)).background(Panel2).clickable {
        runCatching {
            val intent = android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(stream.url))
            context.startActivity(intent)
        }
    }.padding(14.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (stream.iconUrl.isNotBlank()) BadgeImage(stream.iconUrl, "LIVE", Modifier.size(34.dp)) else SportGlyph("LIVE", 34.dp)
            Spacer(Modifier.width(9.dp))
            Column(Modifier.weight(1f)) {
                Text("FREE", color = Color(0xFF74FFAA), fontSize = 8.sp, fontWeight = FontWeight.Black)
                Text(stream.sourceName, color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
        Spacer(Modifier.height(9.dp))
        Text(stream.name, color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.Black, maxLines = 2, overflow = TextOverflow.Ellipsis)
        Text(stream.group, color = Muted, fontSize = 9.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
        Spacer(Modifier.height(8.dp))
        Text("WATCH →", color = XRed, fontSize = 9.sp, fontWeight = FontWeight.Black)
    }
}

'''
s, count = pattern.subn(replacement, s, count=1)
if count != 1:
    raise SystemExit("Could not locate MobileLiveCenter block")

FUT.write_text(s, encoding="utf-8")

# TV: use the same public registry/resolver and put healthy public streams on the
# TV home screen. Xtream/M3U remains a separate private-source path.
if TV.is_file():
    tv = TV.read_text(encoding="utf-8")
    if 'var publicStreams by remember' not in tv:
        tv = tv.replace(
            'var selectedNav by remember{mutableStateOf("HOME")}',
            'var selectedNav by remember{mutableStateOf("HOME")}\n'
            '    var publicStreams by remember{mutableStateOf<List<PublicResolvedStream>>(emptyList())}\n'
            '    var publicPlayer by remember{mutableStateOf<PublicResolvedStream?>(null)}\n'
            '    LaunchedEffect(Unit){ publicStreams = runCatching{PublicSourceResolver().load()}.getOrDefault(emptyList()) }',
            1
        )
    if 'if(publicPlayer!=null){NativePlayerScreen' not in tv:
        tv = tv.replace(
            'Box(Modifier.fillMaxSize().background(TvBg)){',
            'if(publicPlayer!=null){NativePlayerScreen(publicPlayer!!.url,publicPlayer!!.name){publicPlayer=null};return}\n    Box(Modifier.fillMaxSize().background(TvBg)){',
            1
        )
    if '@Composable private fun TvPublicSourceRow' not in tv:
        tv += '''

@Composable
private fun TvPublicSourceRow(streams: List<PublicResolvedStream>, onPlay: (PublicResolvedStream)->Unit) {
    if (streams.isEmpty()) return
    TvSection("FREE SPORTS SOURCES", "${streams.size} HEALTHY")
    Spacer(Modifier.height(10.dp))
    LazyRow(horizontalArrangement=Arrangement.spacedBy(10.dp), contentPadding=PaddingValues(end=8.dp)) {
        items(streams.take(16), key={it.url}) { stream ->
            Column(
                Modifier.width(210.dp).height(92.dp).clip(RoundedCornerShape(14.dp))
                    .background(TvPanel2)
                    .border(1.dp,TvBlue.copy(alpha=.25f),RoundedCornerShape(14.dp))
                    .focusable().clickable{onPlay(stream)}.padding(12.dp)
            ) {
                Text("PUBLIC • ${stream.sourceName}",color=Color(0xFF74FFAA),fontSize=8.sp,fontWeight=FontWeight.Black,maxLines=1,overflow=TextOverflow.Ellipsis)
                Spacer(Modifier.height(6.dp))
                Text(stream.name,color=Color.White,fontSize=11.sp,fontWeight=FontWeight.Black,maxLines=2,overflow=TextOverflow.Ellipsis)
                Spacer(Modifier.height(5.dp))
                Text(stream.group,color=TvMuted,fontSize=8.sp,maxLines=1,overflow=TextOverflow.Ellipsis)
            }
        }
    }
}
'''
    # Add the public-source rail only once, preserving the existing network rail.
    if 'TvPublicSourceRow(publicStreams)' not in tv:
        tv = tv.replace(
            'TvNetworkGrid(tvNetworks,onNetwork)',
            'TvNetworkGrid(tvNetworks,onNetwork);Spacer(Modifier.height(18.dp));TvPublicSourceRow(publicStreams){publicPlayer=it}',
            1
        )
    TV.write_text(tv, encoding="utf-8")

print("Public free-source UI patch: mobile + TV public-first flow wired")
