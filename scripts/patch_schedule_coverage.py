#!/usr/bin/env python3
from pathlib import Path

SERVICE = Path('app/src/main/java/com/xsportsx/app/SportsScheduleService.kt')
SCREEN = Path('app/src/main/java/com/xsportsx/app/SportsScheduleScreen.kt')

# Expand the live/schedule API coverage. These are real ESPN scoreboard slugs;
# multiple entries may share one canonical UI league (NCAA VB combines men's
# and women's volleyball).
LEAGUE_BLOCK = '''        ScheduleLeague("WNBA", "Basketball", "basketball/wnba", "https://www.wnba.com/"),
        ScheduleLeague("NCAA BASEBALL", "Baseball", "baseball/college-baseball", "https://www.ncaa.com/sports/baseball"),
        ScheduleLeague("NCAA MEN HOCKEY", "Hockey", "hockey/mens-college-hockey", "https://www.ncaa.com/sports/icehockey-men/d1"),
        ScheduleLeague("NCAA WOMEN HOCKEY", "Hockey", "hockey/womens-college-hockey", "https://www.ncaa.com/sports/icehockey-women/d1"),
        ScheduleLeague("NCAA SOFTBALL", "Softball", "softball/college-softball", "https://www.ncaa.com/sports/softball"),
        ScheduleLeague("NCAA VB", "Volleyball", "volleyball/womens-college-volleyball", "https://www.ncaa.com/sports/volleyball-women/d1"),
        ScheduleLeague("NCAA VB", "Volleyball", "volleyball/mens-college-volleyball", "https://www.ncaa.com/sports/volleyball-men/d1"),
        ScheduleLeague("NCAA MEN SOCCER", "Soccer", "soccer/usa.ncaa.m.1", "https://www.ncaa.com/sports/soccer-men/d1"),
        ScheduleLeague("NCAA WOMEN SOCCER", "Soccer", "soccer/usa.ncaa.w.1", "https://www.ncaa.com/sports/soccer-women/d1"),
        ScheduleLeague("NCAA MEN LAX", "Lacrosse", "lacrosse/mens-college-lacrosse", "https://www.ncaa.com/sports/lacrosse-men/d1"),
        ScheduleLeague("NCAA WOMEN LAX", "Lacrosse", "lacrosse/womens-college-lacrosse", "https://www.ncaa.com/sports/lacrosse-women/d1"),
        ScheduleLeague("MLS", "Soccer", "soccer/usa.1", "https://www.mlssoccer.com/"),
        ScheduleLeague("EPL", "Soccer", "soccer/eng.1", "https://www.premierleague.com/"),
        ScheduleLeague("LaLiga", "Soccer", "soccer/esp.1", "https://www.laliga.com/"),
        ScheduleLeague("Bundesliga", "Soccer", "soccer/ger.1", "https://www.bundesliga.com/"),
        ScheduleLeague("Serie A", "Soccer", "soccer/ita.1", "https://www.legaseriea.it/"),
        ScheduleLeague("Ligue 1", "Soccer", "soccer/fra.1", "https://www.ligue1.com/"),
        ScheduleLeague("UCL", "Soccer", "soccer/uefa.champions", "https://www.uefa.com/uefachampionsleague/"),
        ScheduleLeague("UEL", "Soccer", "soccer/uefa.europa", "https://www.uefa.com/uefaeuropaleague/"),
        ScheduleLeague("NWSL", "Soccer", "soccer/usa.nwsl", "https://www.nwslsoccer.com/"),
'''

s = SERVICE.read_text(encoding='utf-8')
if 'ScheduleLeague("WNBA"' not in s:
    marker = '        ScheduleLeague("UFC", "MMA", "mma/ufc", "https://www.ufc.com/"),\n'
    if marker not in s:
        raise SystemExit('league insertion marker not found')
    s = s.replace(marker, LEAGUE_BLOCK + marker, 1)

# The ESPN MMA scoreboard contains event-level fights/cards where one or both
# competitors can be absent. Do not discard the entire event just because the
# team-style fields are empty; the dedicated UFC/boxing card can render title.
s = s.replace(
    '            if (start.isBlank() || home.isBlank() || away.isBlank()) continue\n',
    '            if (start.isBlank()) continue\n',
    1,
)

# Give missing combat participants a meaningful event label instead of HOME/AWAY.
s = s.replace(
    '            val title = rawName.ifBlank { "$away vs $home" }\n',
    '            val title = rawName.ifBlank {\n                when {\n                    home.isNotBlank() && away.isNotBlank() -> "$away vs $home"\n                    home.isNotBlank() -> home\n                    away.isNotBlank() -> away\n                    else -> league.league\n                }\n            }\n',
    1,
)

# The special feed is also used for combat promotions that do not expose a
# reliable ESPN scoreboard (especially boxing). Keep UFC on ESPN to avoid
# duplicate cards, but allow BOXING to come from the maintained special feed.
s = s.replace(
    'setOf("WRESTLING", "WWE", "AEW", "TNA", "WRC", "WEC", "IMSA", "FORMULA E", "MXGP", "MONSTER JAM", "MOTOGP", "F1")',
    'setOf("WRESTLING", "WWE", "AEW", "TNA", "WRC", "WEC", "IMSA", "FORMULA E", "MXGP", "MONSTER JAM", "MOTOGP", "F1", "BOXING")',
    1,
)
SERVICE.write_text(s, encoding='utf-8')

# Final UI catalog: expose the same leagues the service can actually back.
t = SCREEN.read_text(encoding='utf-8')
start = t.find('    val leagueChoices = listOf(')
if start >= 0:
    end = t.find('    )', start)
    if end >= 0:
        end += len('    )')
        choices = '''    val leagueChoices = listOf(
        "ALL", "NFL", "NBA", "WNBA", "NCAA FB", "NCAA FCS", "NCAA BB", "NCAA WBB",
        "MLB", "NCAA BASEBALL", "NHL", "NCAA MEN HOCKEY", "NCAA WOMEN HOCKEY", "NCAA SOFTBALL",
        "NCAA VB", "NCAA MEN SOCCER", "NCAA WOMEN SOCCER", "NCAA MEN LAX", "NCAA WOMEN LAX", "NCAA WRESTLING",
        "MLS", "EPL", "LaLiga", "Bundesliga", "Serie A", "Ligue 1", "UCL", "UEL", "NWSL",
        "UFC", "BOXING", "RUGBY", "F1", "NASCAR", "INDYCAR", "WRESTLING", "WRC", "WEC", "IMSA",
        "FORMULA E", "MXGP", "MONSTER JAM", "MOTOGP"
    )'''
        t = t[:start] + choices + t[end:]

# Special motorsport events must not all be labeled "F1 • GRAND PRIX".
old_eyebrow = '''                    Text(when { event.league.equals("UFC", true) -> "UFC • FIGHT EVENT"; event.league.equals("BOXING", true) -> "BOXING • EVENT NIGHT"; else -> "F1 • GRAND PRIX" }, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black, letterSpacing = 1.4.sp)'''
new_eyebrow = '''                    Text(eventCardEyebrow(event), color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black, letterSpacing = 1.4.sp)'''
if old_eyebrow in t:
    t = t.replace(old_eyebrow, new_eyebrow, 1)

if 'private fun eventCardEyebrow(event: SportsEvent): String' not in t:
    marker = '@Composable\nprivate fun EventArtBadge'
    helper = '''private fun eventCardEyebrow(event: SportsEvent): String = when {
    event.league.equals("UFC", true) -> "UFC • FIGHT EVENT"
    event.league.equals("BOXING", true) -> "BOXING • EVENT NIGHT"
    event.league.equals("FORMULA E", true) -> "FORMULA E • ePRIX"
    event.league.equals("MXGP", true) -> "MXGP • GRAND PRIX"
    event.league.equals("MONSTER JAM", true) -> "MONSTER JAM • EVENT"
    event.league.equals("MOTOGP", true) -> "MOTOGP • GRAND PRIX"
    event.league.equals("WRC", true) -> "WRC • RALLY"
    event.league.equals("WEC", true) -> "WEC • ENDURANCE"
    event.league.equals("IMSA", true) -> "IMSA • RACE"
    event.league.equals("F1", true) -> "F1 • GRAND PRIX"
    else -> event.league.uppercase()
}

'''
    if marker not in t:
        raise SystemExit('event art marker not found')
    t = t.replace(marker, helper + marker, 1)

old_badge = 'Text(if (isUfc) "UFC" else "BOXING", color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Black, letterSpacing = 1.4.sp)'
new_badge = 'Text(if (isUfc) "UFC" else if (event.league.equals("BOXING", true)) "BOXING" else event.league.uppercase(), color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.Black, letterSpacing = 1.0.sp)'
if old_badge in t:
    t = t.replace(old_badge, new_badge, 1)

SCREEN.write_text(t, encoding='utf-8')
print('Schedule coverage expanded; empty combat events preserved; special event cards use their real league labels')
