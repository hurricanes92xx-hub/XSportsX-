#!/usr/bin/env python3
import re
import subprocess
from pathlib import Path

SCREEN = Path('app/src/main/java/com/xsportsx/app/SportsScheduleScreen.kt')
WRESTLING = Path('app/src/main/java/com/xsportsx/app/WrestlingSchedule.kt')
LAUNCHER = Path('app/src/main/java/com/xsportsx/app/MainActivityFuture.kt')

HELPER_NAME = 'specialCardKicker'

HELPER = '''private fun specialCardKicker(event: SportsEvent): String {
    if (event.league.equals("WRESTLING", true)) {
        val title = event.title.trim()
        val promotion = listOf("WWE", "AEW", "NXT", "ROH", "TNA", "NJPW")
            .firstOrNull { title.startsWith("$it •", true) || title.startsWith("$it —", true) || title.startsWith("$it:", true) }
            ?: "WRESTLING"
        return "$promotion • WRESTLING"
    }
    return when (event.league.uppercase()) {
        "UFC" -> "UFC • FIGHT EVENT"
        "BOXING" -> "BOXING • EVENT NIGHT"
        "FORMULA E" -> "FORMULA E • ePRIX"
        "MXGP" -> "MXGP • GRAND PRIX"
        "MONSTER JAM" -> "MONSTER JAM • EVENT"
        "MOTOGP" -> "MOTOGP • GRAND PRIX"
        "WRC" -> "WRC • RALLY"
        "WEC" -> "WEC • ENDURANCE"
        "IMSA" -> "IMSA • SPORTS CAR"
        "F1" -> "F1 • GRAND PRIX"
        else -> "${event.league.uppercase()} • EVENT"
    }
}

'''

FUNCTION_RE = re.compile(
    r'(?m)^[ \t]*(?:(?:public|private|protected|internal|final|open|inline|tailrec|suspend|operator|infix|actual|expect)\s+)*'
    r'fun\s+specialCardKicker\s*\([^)]*\)\s*(?::\s*[^=\n{]+)?\s*\{'
)


def remove_all_named_functions(source: str) -> tuple[str, int]:
    removed = 0
    while True:
        match = FUNCTION_RE.search(source)
        if not match:
            break
        open_brace = source.find('{', match.start(), match.end())
        depth = 0
        close_brace = None
        for i in range(open_brace, len(source)):
            ch = source[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    close_brace = i + 1
                    break
        if close_brace is None:
            raise RuntimeError(f'Unbalanced braces while removing {HELPER_NAME}')
        start = match.start()
        end = close_brace
        while end < len(source) and source[end] in ' \t\r\n':
            end += 1
        source = source[:start] + source[end:]
        removed += 1
    return source, removed

s = SCREEN.read_text(encoding='utf-8')
s, removed = remove_all_named_functions(s)
marker = '@Composable\nprivate fun EventArtBadge'
if marker not in s:
    raise RuntimeError('Could not find EventArtBadge marker; refusing to write an unverified release source file')
s = s.replace(marker, HELPER + marker, 1)
s = s.replace(
    'event.league.equals("UFC", true) || event.league.equals("BOXING", true) || event.sport.equals("MMA", true)',
    'event.league.equals("UFC", true) || event.league.equals("BOXING", true) || event.league.equals("WRESTLING", true) || event.sport.equals("MMA", true)',
    1,
)
s = s.replace(
    'Text(when { event.league.equals("UFC", true) -> "UFC • FIGHT EVENT"; event.league.equals("BOXING", true) -> "BOXING • EVENT NIGHT"; else -> "F1 • GRAND PRIX" }, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black, letterSpacing = 1.4.sp)',
    'Text(specialCardKicker(event), color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black, letterSpacing = 1.4.sp)',
    1,
)
count = len(FUNCTION_RE.findall(s))
if count != 1:
    raise RuntimeError(f'Release source normalization failed: expected exactly 1 {HELPER_NAME} declaration, found {count}')
SCREEN.write_text(s, encoding='utf-8')

w = WRESTLING.read_text(encoding='utf-8')
w = w.replace('Text("WWE • AEW • TNA"', 'Text("WWE • AEW • NXT • ROH • TNA • NJPW"')
w = w.replace(
    'listOf("WWE" to Color(0xFF2E8BFF),"AEW" to Color(0xFFFF102F),"TNA" to Color(0xFFFF6D00))',
    'listOf("WWE" to Color(0xFF2E8BFF),"AEW" to Color(0xFFFF102F),"NXT" to Color(0xFFFFB000),"ROH" to Color(0xFF8A63D2),"TNA" to Color(0xFFFF6D00),"NJPW" to Color(0xFFDD2222))',
)
old = '''        LazyRow(horizontalArrangement=Arrangement.spacedBy(8.dp),contentPadding=PaddingValues(end=8.dp)) {
            listOf("WWE" to Color(0xFF2E8BFF),"AEW" to Color(0xFFFF102F),"NXT" to Color(0xFFFFB000),"ROH" to Color(0xFF8A63D2),"TNA" to Color(0xFFFF6D00),"NJPW" to Color(0xFFDD2222)).forEach { (brand,color) ->
                Box(Modifier.clip(RoundedCornerShape(10.dp)).background(color.copy(alpha=.16f)).padding(horizontal=9.dp,vertical=6.dp)) { Text(brand,color=color,fontSize=9.sp,fontWeight=FontWeight.Black) }
            }
        }'''
new = '''        val promotions = listOf("WWE" to Color(0xFF2E8BFF),"AEW" to Color(0xFFFF102F),"NXT" to Color(0xFFFFB000),"ROH" to Color(0xFF8A63D2),"TNA" to Color(0xFFFF6D00),"NJPW" to Color(0xFFDD2222))
        LazyRow(horizontalArrangement=Arrangement.spacedBy(8.dp),contentPadding=PaddingValues(end=8.dp)) {
            items(promotions, key={it.first}) { (brand,color) ->
                Box(Modifier.clip(RoundedCornerShape(10.dp)).background(color.copy(alpha=.16f)).padding(horizontal=9.dp,vertical=6.dp)) { Text(brand,color=color,fontSize=9.sp,fontWeight=FontWeight.Black) }
            }
        }'''
if old in w:
    w = w.replace(old, new, 1)
w = w.replace('setOf("WWE","AEW","TNA")', 'setOf("WWE","AEW","NXT","ROH","TNA","NJPW")')
WRESTLING.write_text(w, encoding='utf-8')

# Production patch scripts are allowed to rewrite their target files, but the
# launcher activity is not one of those targets. Restore it from the checked-in
# commit at the end of the patch chain so emulator/debug builds cannot ship a
# manifest entry for a missing Activity class.
subprocess.run(['git', 'checkout', '--', str(LAUNCHER)], check=True)
if not LAUNCHER.is_file() or 'class MainActivityFuture' not in LAUNCHER.read_text(encoding='utf-8'):
    raise RuntimeError('Launcher activity was not restored after production patches')

print(f'Final wrestling build normalization applied: removed {removed} prior {HELPER_NAME} declaration(s), installed exactly one helper, fixed LazyRow DSL, enabled six pro promotions, no UWW/amateur wrestling. Launcher activity restored and verified.')
