from pathlib import Path

# Ticker: let each league/news group finish one full marquee pass before advancing.
ticker = Path('app/src/main/java/com/xsportsx/app/HomeSportsTicker.kt')
s = ticker.read_text()
if 'private fun TickerMarquee(' not in s:
    s = s.replace('import androidx.compose.foundation.layout.*\n', 'import androidx.compose.foundation.layout.*\nimport androidx.compose.foundation.layout.BoxWithConstraints\n', 1)
    s = s.replace('import androidx.compose.ui.Modifier\n', 'import androidx.compose.ui.Modifier\nimport androidx.compose.ui.layout.onSizeChanged\nimport androidx.compose.ui.platform.LocalDensity\n', 1)
    start = s.index('@Composable\nfun HomeSportsTicker(')
    replacement = '''@Composable
fun HomeSportsTicker(modifier: Modifier = Modifier) {
    var groups by remember { mutableStateOf<List<TickerLeagueGroup>>(emptyList()) }
    var index by remember { mutableIntStateOf(0) }
    var loading by remember { mutableStateOf(true) }
    var failed by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        while (isActive) {
            loading = true
            val loaded = runCatching { loadTickerGroups() }.getOrDefault(emptyList())
            if (loaded.isNotEmpty()) {
                groups = loaded
                index = index.coerceIn(0, loaded.lastIndex)
                failed = false
            } else if (groups.isEmpty()) {
                failed = true
            }
            loading = false
            delay(60_000L)
        }
    }

    val group = groups.getOrNull(index.coerceIn(0, (groups.size - 1).coerceAtLeast(0)))
    val text = group?.let(::line)?.takeIf { it.isNotBlank() } ?: when {
        loading -> "SPORTS FEED  •  LOADING"
        failed -> "SPORTS FEED  •  TEMPORARILY UNAVAILABLE"
        else -> "SPORTS FEED  •  NO GAMES / NEWS AVAILABLE"
    }

    Row(
        modifier.fillMaxWidth().height(42.dp).background(Color(0xEE07090E)).padding(horizontal = 18.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text("X", color = Color(0xFFFF1744), fontWeight = FontWeight.Black, fontSize = 20.sp)
        Spacer(Modifier.width(10.dp))
        TickerMarquee(text) {
            if (groups.size > 1) index = (index + 1) % groups.size
        }
    }
}

@Composable
private fun TickerMarquee(text: String, onFinished: () -> Unit) {
    val density = LocalDensity.current
    var viewportWidthPx by remember { mutableIntStateOf(0) }
    var textWidthPx by remember(text) { mutableIntStateOf(0) }

    LaunchedEffect(text, viewportWidthPx, textWidthPx) {
        if (viewportWidthPx <= 0 || textWidthPx <= 0) return@LaunchedEffect
        val velocityPxPerSecond = with(density) { 55.dp.toPx() }
        val duration = if (textWidthPx <= viewportWidthPx) {
            4_500L
        } else {
            ((textWidthPx + viewportWidthPx) / velocityPxPerSecond * 1_000L + 900L).toLong().coerceAtLeast(5_000L)
        }
        delay(duration)
        onFinished()
    }

    BoxWithConstraints(
        Modifier.weight(1f).fillMaxHeight().onSizeChanged { viewportWidthPx = it.width }
    ) {
        Text(
            text,
            modifier = Modifier
                .fillMaxWidth()
                .basicMarquee(
                    iterations = 1,
                    repeatDelayMillis = 0,
                    initialDelayMillis = 650,
                    velocity = 55.dp
                ),
            onTextLayout = { textWidthPx = it.size.width },
            color = Color.White,
            fontWeight = FontWeight.Bold,
            fontSize = 12.sp,
            maxLines = 1
        )
    }
}
'''
    s = s[:start] + replacement
    ticker.write_text(s)

# Mobile: make the existing XSportsX cracks substantially thicker/brighter.
mobile = Path('app/src/main/java/com/xsportsx/app/FuturisticSports.kt')
ms = mobile.read_text()
ms = ms.replace('strokeWidth = 11f)', 'strokeWidth = 20f)', 1)
ms = ms.replace('strokeWidth = 4f)', 'strokeWidth = 7f)', 1)
ms = ms.replace('strokeWidth = 1.3f)', 'strokeWidth = 2.1f)', 1)
mobile.write_text(ms)

# TV: add a matching thick red crack layer behind the 10-foot UI.
tv = Path('app/src/main/java/com/xsportsx/app/TvHome.kt')
ts = tv.read_text()
if 'import androidx.compose.foundation.Canvas' not in ts:
    ts = ts.replace('import androidx.compose.foundation.background\n', 'import androidx.compose.foundation.Canvas\nimport androidx.compose.foundation.background\n', 1)
if 'private fun TvGlowingCracks(' not in ts:
    ts = ts.replace(
        'Box(Modifier.fillMaxSize().background(TvBg)) {\n        Row(Modifier.fillMaxSize()) {',
        'Box(Modifier.fillMaxSize().background(TvBg)) {\n        TvGlowingCracks(Modifier.fillMaxSize())\n        Row(Modifier.fillMaxSize()) {',
        1,
    )
    ts += '''\n\n@Composable\nprivate fun TvGlowingCracks(modifier: Modifier) {\n    Canvas(modifier) {\n        val w = size.width\n        val h = size.height\n        val lines = listOf(\n            listOf(.00f to .20f, .11f to .25f, .16f to .34f, .29f to .38f),\n            listOf(1.00f to .17f, .88f to .24f, .83f to .34f, .69f to .40f),\n            listOf(.03f to .77f, .16f to .72f, .23f to .61f, .37f to .57f),\n            listOf(.97f to .73f, .85f to .67f, .79f to .56f, .64f to .51f),\n            listOf(.43f to .00f, .47f to .10f, .53f to .18f, .60f to .27f)\n        )\n        lines.forEach { points ->\n            for (i in 0 until points.lastIndex) {\n                val a = points[i]\n                val b = points[i + 1]\n                val start = androidx.compose.ui.geometry.Offset(a.first * w, a.second * h)\n                val end = androidx.compose.ui.geometry.Offset(b.first * w, b.second * h)\n                drawLine(TvRed.copy(alpha = .10f), start, end, strokeWidth = 24f)\n                drawLine(TvRed.copy(alpha = .20f), start, end, strokeWidth = 10f)\n                drawLine(TvRed.copy(alpha = .72f), start, end, strokeWidth = 3f)\n            }\n        }\n    }\n}\n'''
tv.write_text(ts)

# Bump the signed APK version so installed 1.6.3 builds can receive this fix in-app.
gradle = Path('app/build.gradle.kts')
gs = gradle.read_text()
gs = gs.replace('versionCode = 14', 'versionCode = 15', 1)
gs = gs.replace('versionName = "1.6.3"', 'versionName = "1.6.4"', 1)
gradle.write_text(gs)

print('ticker/crack patch ready')
