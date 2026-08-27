#!/usr/bin/env python3
from pathlib import Path

SERVICE = Path('app/src/main/java/com/xsportsx/app/SportsScheduleService.kt')
SCREEN = Path('app/src/main/java/com/xsportsx/app/SportsScheduleScreen.kt')
TV = Path('app/src/main/java/com/xsportsx/app/TvHome.kt')
MOBILE = Path('app/src/main/java/com/xsportsx/app/FuturisticSports.kt')

# Professional wrestling only. UWW/college/amateur wrestling is intentionally excluded.
s = SERVICE.read_text(encoding='utf-8')
s = s.replace(
    'private val SPECIAL_FEED_LEAGUES = setOf("WRESTLING", "WWE", "AEW", "TNA", "WRC", "WEC", "IMSA", "FORMULA E", "MXGP", "MONSTER JAM", "MOTOGP", "F1")',
    'private val SPECIAL_FEED_LEAGUES = setOf("WRESTLING", "WWE", "AEW", "NXT", "ROH", "TNA", "NJPW", "WRC", "WEC", "IMSA", "FORMULA E", "MXGP", "MONSTER JAM", "MOTOGP", "F1")',
    1,
)
s = s.replace('"WWE", "AEW", "TNA" -> "WRESTLING"', '"WWE", "AEW", "NXT", "ROH", "TNA", "NJPW" -> "WRESTLING"', 1)
s = s.replace('"NCAA WRESTLING", ', '', 1)
SERVICE.write_text(s, encoding='utf-8')

# Remove any old UWW badge/source association and keep the rail WWE-branded.
for path in (TV, MOBILE):
    t = path.read_text(encoding='utf-8')
    t = t.replace('TvSport("WRESTLING","WR","https://www.google.com/s2/favicons?domain=uww.org&sz=128")', 'TvSport("WRESTLING","WWE","")')
    t = t.replace('SportVisual("WRESTLING", "WR", "https://commons.wikimedia.org/wiki/Special:FilePath/WWE_Official_Logo.svg?width=256")', 'SportVisual("WRESTLING", "WWE", "https://commons.wikimedia.org/wiki/Special:FilePath/WWE_Official_Logo.svg?width=256")')
    t = t.replace('WWE • AEW • TNA', 'WWE • AEW • NXT • ROH • TNA • NJPW')
    path.write_text(t, encoding='utf-8')

# Route wrestling through the event-style card so fake AI vs W / NH vs W placeholders disappear.
t = SCREEN.read_text(encoding='utf-8')
t = t.replace(
    'val combat = event.league.equals("UFC", true) || event.league.equals("BOXING", true) || event.sport.equals("MMA", true)',
    'val combat = event.league.equals("UFC", true) || event.league.equals("BOXING", true) || event.league.equals("WRESTLING", true) || event.sport.equals("MMA", true)',
    1,
)
old_label = 'Text(when { event.league.equals("UFC", true) -> "UFC • FIGHT EVENT"; event.league.equals("BOXING", true) -> "BOXING • EVENT NIGHT"; else -> "F1 • GRAND PRIX" }, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black, letterSpacing = 1.4.sp)'
t = t.replace(old_label, 'Text(specialCardKicker(event), color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black, letterSpacing = 1.4.sp)', 1)
if 'private val PRO_WRESTLING_PROMOTIONS' not in t:
    t = t.replace('@Composable\nprivate fun EventArtBadge', 'private val PRO_WRESTLING_PROMOTIONS = listOf("WWE", "AEW", "NXT", "ROH", "TNA", "NJPW")\n\nprivate fun specialCardKicker(event: SportsEvent): String {\n    if (event.league.equals("WRESTLING", true)) {\n        val title = event.title.trim()\n        val promotion = PRO_WRESTLING_PROMOTIONS.firstOrNull { title.startsWith("$it •", true) || title.startsWith("$it —", true) || title.startsWith("$it:", true) } ?: "WRESTLING"\n        return "$promotion • WRESTLING"\n    }\n    return when (event.league.uppercase()) {\n        "UFC" -> "UFC • FIGHT EVENT"\n        "BOXING" -> "BOXING • EVENT NIGHT"\n        "FORMULA E" -> "FORMULA E • ePRIX"\n        "MXGP" -> "MXGP • GRAND PRIX"\n        "MONSTER JAM" -> "MONSTER JAM • EVENT"\n        "MOTOGP" -> "MOTOGP • GRAND PRIX"\n        "WRC" -> "WRC • RALLY"\n        "WEC" -> "WEC • ENDURANCE"\n        "IMSA" -> "IMSA • SPORTS CAR"\n        "F1" -> "F1 • GRAND PRIX"\n        else -> "${event.league.uppercase()} • EVENT"\n    }\n}\n\n@Composable\nprivate fun EventArtBadge', 1)
SCREEN.write_text(t, encoding='utf-8')

print('Professional wrestling schedule patch applied: WWE, AEW, NXT, ROH, TNA, NJPW; UWW/amateur wrestling removed; event cards use real promotion/event names.')
