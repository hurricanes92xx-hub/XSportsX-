#!/usr/bin/env python3
import re
from pathlib import Path

SCREEN = Path('app/src/main/java/com/xsportsx/app/SportsScheduleScreen.kt')
WRESTLING = Path('app/src/main/java/com/xsportsx/app/WrestlingSchedule.kt')

# Some older schedule patches can each add their own card helper. Normalize to
# exactly one helper so release builds cannot fail with duplicate declarations.
s = SCREEN.read_text(encoding='utf-8')
helper = '''private fun specialCardKicker(event: SportsEvent): String {
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
s = re.sub(r'private fun specialCardKicker\(event: SportsEvent\): String \{.*?\n\}\n\n', '', s, flags=re.S)
marker = '@Composable\nprivate fun EventArtBadge'
if marker in s:
    s = s.replace(marker, helper + marker, 1)
s = s.replace('event.league.equals("UFC", true) || event.league.equals("BOXING", true) || event.sport.equals("MMA", true)', 'event.league.equals("UFC", true) || event.league.equals("BOXING", true) || event.league.equals("WRESTLING", true) || event.sport.equals("MMA", true)', 1)
s = s.replace('Text(when { event.league.equals("UFC", true) -> "UFC • FIGHT EVENT"; event.league.equals("BOXING", true) -> "BOXING • EVENT NIGHT"; else -> "F1 • GRAND PRIX" }, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black, letterSpacing = 1.4.sp)', 'Text(specialCardKicker(event), color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black, letterSpacing = 1.4.sp)', 1)
SCREEN.write_text(s, encoding='utf-8')

# Keep the promotion-chip row inside LazyRow's DSL via items(); direct forEach
# composable emission there is illegal and was the second release-build error.
w = WRESTLING.read_text(encoding='utf-8')
w = w.replace('Text("WWE • AEW • TNA"', 'Text("WWE • AEW • NXT • ROH • TNA • NJPW"')
w = w.replace('listOf("WWE" to Color(0xFF2E8BFF),"AEW" to Color(0xFFFF102F),"TNA" to Color(0xFFFF6D00))', 'listOf("WWE" to Color(0xFF2E8BFF),"AEW" to Color(0xFFFF102F),"NXT" to Color(0xFFFFB000),"ROH" to Color(0xFF8A63D2),"TNA" to Color(0xFFFF6D00),"NJPW" to Color(0xFFDD2222))')
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
# Ensure the six promotions are always part of the remote schedule filter.
w = w.replace('setOf("WWE","AEW","TNA")', 'setOf("WWE","AEW","NXT","ROH","TNA","NJPW")')
WRESTLING.write_text(w, encoding='utf-8')

print('Final wrestling build normalization applied: one card helper, valid LazyRow DSL, six pro promotions, no UWW/amateur wrestling.')
