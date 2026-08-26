from pathlib import Path
import re

p = Path('app/src/main/java/com/xsportsx/app/MainActivity.kt')
s = p.read_text(encoding='utf-8')

live_old = '''@Composable
fun LiveScreen(onGame: (Game) -> Unit) {
    Column(Modifier.fillMaxSize()) {
        Header("LIVE NOW", "Streams become available when your connected source matches the event")
        val live = games.filter { it.league == "NFL" || it.league == "MLB" }
        if (live.isEmpty()) EmptyState("Nothing live right now") else LazyColumn(contentPadding = PaddingValues(34.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) { items(live) { LiveRow(it, onGame) } }
    }
}
'''
live_new = '''@Composable
fun LiveScreen(onGame: (Game) -> Unit) {
    // Public/authorized sources are always checked first. Xtream/M3U remains optional.
    LiveChannelsScreen(filter = null, onBack = { })
}
'''
if live_old not in s:
    raise SystemExit('LiveScreen block not found')
s = s.replace(live_old, live_new, 1)

pattern = re.compile(r'@Composable\nfun EventSheet\(game: Game, onClose: \(\) -> Unit\) \{.*\}\s*$', re.DOTALL)
replacement = '''@Composable
fun EventSheet(game: Game, onClose: () -> Unit) {
    var browsePublic by remember { mutableStateOf(false) }
    if (browsePublic) {
        val publicFilter = game.matchup.replace(Regex("\\\\s+vs\\\\s+", RegexOption.IGNORE_CASE), "||")
        LiveChannelsScreen(filter = publicFilter, onBack = { browsePublic = false })
        return
    }
    Box(Modifier.fillMaxSize().background(Color(0x99000000)), contentAlignment = Alignment.BottomCenter) {
        Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(topStart = 30.dp, topEnd = 30.dp)).background(Color(0xFF10131A)).padding(28.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(game.icon, fontSize = 42.sp)
                Spacer(Modifier.width(16.dp))
                Column(Modifier.weight(1f)) {
                    Text(game.matchup, color = Color.White, fontSize = 21.sp, fontWeight = FontWeight.Black)
                    Text(game.league + " • " + game.time, color = Color(0xFF8A919E))
                }
                TextButton(onClick = onClose) { Text("CLOSE") }
            }
            Spacer(Modifier.height(22.dp))
            Text("LIVE SOURCE MATCHING", color = Color(0xFFFF536C), fontWeight = FontWeight.Black, letterSpacing = 1.2.sp)
            Text("XSportsX checks public/authorized sources first. Xtream/M3U is optional and only adds your own source.", color = Color(0xFF9AA1AE), fontSize = 13.sp)
            Spacer(Modifier.height(18.dp))
            Button(
                onClick = { browsePublic = true },
                Modifier.fillMaxWidth().height(52.dp),
                shape = RoundedCornerShape(15.dp)
            ) { Text("FIND LIVE SOURCES — NO LOGIN", fontWeight = FontWeight.Black) }
        }
    }
}
'''
s, count = pattern.subn(replacement, s, count=1)
if count != 1:
    raise SystemExit('EventSheet block not found')

p.write_text(s, encoding='utf-8')
print('Public-first live source flow applied: Live tab and event sheet no longer require Xtream/M3U login.')
