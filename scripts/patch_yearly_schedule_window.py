#!/usr/bin/env python3
from pathlib import Path
import re

SERVICE = Path('app/src/main/java/com/xsportsx/app/SportsScheduleService.kt')
SCREEN = Path('app/src/main/java/com/xsportsx/app/SportsScheduleScreen.kt')

s = SERVICE.read_text(encoding='utf-8')

s = re.sub(r'(const\s+val\s+DAYS_AHEAD\s*=\s*)\d+L?', r'\g<1>30L', s, count=1)
if 'const val DAYS_AHEAD' not in s:
    s = s.replace('object SportsScheduleService {', 'object SportsScheduleService {\n    private const val DAYS_AHEAD = 30L', 1)

registry = '''    private val leagues = listOf(
        ScheduleLeague("NFL", "Football", "football/nfl", "https://www.nfl.com/"),
        ScheduleLeague("NBA", "Basketball", "basketball/nba", "https://www.nba.com/"),
        ScheduleLeague("WNBA", "Basketball", "basketball/wnba", "https://www.wnba.com/"),
        ScheduleLeague("NCAA FB", "Football", "football/college-football", "https://www.ncaa.com/sports/football/fbs", "groups=80"),
        ScheduleLeague("NCAA FCS", "Football", "football/college-football", "https://www.ncaa.com/sports/football/fcs", "groups=81"),
        ScheduleLeague("NCAA BB", "Basketball", "basketball/mens-college-basketball", "https://www.ncaa.com/sports/basketball-men/d1"),
        ScheduleLeague("NCAA WBB", "Basketball", "basketball/womens-college-basketball", "https://www.ncaa.com/sports/basketball-women/d1"),
        ScheduleLeague("MLB", "Baseball", "baseball/mlb", "https://www.mlb.com/"),
        ScheduleLeague("NCAA BASEBALL", "Baseball", "baseball/college-baseball", "https://www.ncaa.com/sports/baseball"),
        ScheduleLeague("NHL", "Hockey", "hockey/nhl", "https://www.nhl.com/"),
        ScheduleLeague("NCAA MEN HOCKEY", "Hockey", "hockey/mens-college-hockey", "https://www.ncaa.com/sports/icehockey-men/d1"),
        ScheduleLeague("NCAA WOMEN HOCKEY", "Hockey", "hockey/womens-college-hockey", "https://www.ncaa.com/sports/icehockey-women/d1"),
        ScheduleLeague("UFC", "MMA", "mma/ufc", "https://www.ufc.com/"),
        ScheduleLeague("BOXING", "Boxing", "boxing/boxing", "https://www.espn.com/boxing/"),
        ScheduleLeague("MLS", "Soccer", "soccer/usa.1", "https://www.mlssoccer.com/"),
        ScheduleLeague("EPL", "Soccer", "soccer/eng.1", "https://www.premierleague.com/"),
        ScheduleLeague("LaLiga", "Soccer", "soccer/esp.1", "https://www.laliga.com/"),
        ScheduleLeague("Bundesliga", "Soccer", "soccer/ger.1", "https://www.bundesliga.com/"),
        ScheduleLeague("Serie A", "Soccer", "soccer/ita.1", "https://www.legaseriea.it/"),
        ScheduleLeague("Ligue 1", "Soccer", "soccer/fra.1", "https://www.ligue1.com/"),
        ScheduleLeague("UCL", "Soccer", "soccer/uefa.champions", "https://www.uefa.com/uefachampionsleague/"),
        ScheduleLeague("UEL", "Soccer", "soccer/uefa.europa", "https://www.uefa.com/uefaeuropaleague/"),
        ScheduleLeague("NWSL", "Soccer", "soccer/usa.nwsl", "https://www.nwslsoccer.com/"),
        ScheduleLeague("F1", "Racing", "racing/f1", "https://www.formula1.com/"),
        ScheduleLeague("NASCAR", "Racing", "racing/nascar-premier", "https://www.nascar.com/"),
        ScheduleLeague("INDYCAR", "Racing", "racing/irl", "https://www.indycar.com/"),
        ScheduleLeague("NASCAR XFINITY", "Racing", "racing/nascar-secondary", "https://www.nascar.com/"),
        ScheduleLeague("NASCAR TRUCK", "Racing", "racing/nascar-truck", "https://www.nascar.com/"),
        ScheduleLeague("MOTOGP", "Racing", "racing/motogp", "https://www.motogp.com/"),
        ScheduleLeague("RUGBY", "Rugby", "rugby/180659", "https://www.world.rugby/"),
        ScheduleLeague("RUGBY LEAGUE", "Rugby League", "rugby-league/3", "https://www.nrl.com/"),
        ScheduleLeague("LACROSSE", "Lacrosse", "lacrosse/pll", "https://premierlacrosseleague.com/"),
        ScheduleLeague("NLL", "Lacrosse", "lacrosse/nll", "https://www.nll.com/"),
        ScheduleLeague("VOLLEYBALL", "Volleyball", "volleyball/fivb.w", "https://www.fivb.com/"),
        ScheduleLeague("VOLLEYBALL MEN", "Volleyball", "volleyball/fivb.m", "https://www.fivb.com/"),
        ScheduleLeague("GOLF PGA", "Golf", "golf/pga", "https://www.pgatour.com/"),
        ScheduleLeague("GOLF LPGA", "Golf", "golf/lpga", "https://www.lpga.com/"),
        ScheduleLeague("GOLF LIV", "Golf", "golf/liv", "https://www.livgolf.com/"),
        ScheduleLeague("TENNIS ATP", "Tennis", "tennis/atp", "https://www.atptour.com/"),
        ScheduleLeague("TENNIS WTA", "Tennis", "tennis/wta", "https://www.wtatennis.com/"),
        ScheduleLeague("AFL", "Australian Football", "australian-football/afl", "https://www.afl.com.au/")
    )'''

leagues_re = re.compile(r'(?ms)^    private val leagues = listOf\(.*?^    \)\n\n    fun normalizeLeague')
match = leagues_re.search(s)
if not match:
    raise SystemExit('schedule league registry not found: refusing unsafe rewrite')
s = s[:match.start()] + registry + '\n\n    fun normalizeLeague' + s[match.end():]

marker = '        "MONSTER JAM", "MONSTERJAM" -> "MONSTER JAM"\n'
extra_norm = '''        "WNBA" -> "WNBA"
        "NCAA WOMEN'S BASKETBALL", "NCAA WOMENS BASKETBALL" -> "NCAA WBB"
        "NATIONAL WOMEN'S SOCCER LEAGUE" -> "NWSL"
        "MOTOGP" -> "MOTOGP"
        "NASCAR CUP", "NASCAR CUP SERIES" -> "NASCAR"
        "INDYCAR SERIES" -> "INDYCAR"
        "PLL" -> "LACROSSE"
        "ATP" -> "TENNIS ATP"
        "WTA" -> "TENNIS WTA"
        "PGA" -> "GOLF PGA"
        "LPGA" -> "GOLF LPGA"
        "LIV" -> "GOLF LIV"
        "NRL", "SUPER LEAGUE" -> "RUGBY LEAGUE"
'''
if '"WNBA" -> "WNBA"' not in s:
    if marker not in s:
        raise SystemExit('league normalization marker not found')
    s = s.replace(marker, marker + extra_norm, 1)

choices_re = re.compile(r'(?ms)^    val uiLeagueChoices: List<String> = listOf\(.*?^    \)\n\n    suspend fun load')
choices = '''    val uiLeagueChoices: List<String> = listOf(
        "NFL", "NBA", "WNBA", "NCAA FB", "NCAA FCS", "NCAA BB", "NCAA WBB",
        "MLB", "NCAA BASEBALL", "NHL", "NCAA MEN HOCKEY", "NCAA WOMEN HOCKEY",
        "UFC", "BOXING", "MLS", "EPL", "LaLiga", "Bundesliga", "Serie A", "Ligue 1", "UCL", "UEL", "NWSL",
        "F1", "NASCAR", "NASCAR XFINITY", "NASCAR TRUCK", "INDYCAR", "MOTOGP",
        "RUGBY", "RUGBY LEAGUE", "LACROSSE", "NLL", "VOLLEYBALL", "VOLLEYBALL MEN",
        "GOLF PGA", "GOLF LPGA", "GOLF LIV", "TENNIS ATP", "TENNIS WTA", "AFL",
        "WRESTLING", "WRC", "WEC", "IMSA", "FORMULA E", "MXGP", "MONSTER JAM"
    )

    suspend fun load'''
match = choices_re.search(s)
if not match:
    raise SystemExit('ui league choices block not found: refusing unsafe rewrite')
s = s[:match.start()] + choices + s[match.end():]

# Preserve racing/combat/individual events even when ESPN does not provide homeAway.
if 'if (home.isBlank() || away.isBlank()) {' not in s:
    inject_before = '            val rawName = event.optString("name")\n'
    inject = '''            if (home.isBlank() || away.isBlank()) {
                val names = ArrayList<String>()
                for (j in 0 until competitors.length()) {
                    val c = competitors.optJSONObject(j) ?: continue
                    val team = c.optJSONObject("team")
                    val athlete = c.optJSONObject("athlete")
                    val name = team?.optString("displayName")
                        ?.ifBlank { team.optString("shortDisplayName") }
                        ?.ifBlank { athlete?.optString("displayName") }
                        ?.ifBlank { c.optString("displayName") }
                        ?: athlete?.optString("displayName")
                        ?: c.optString("displayName")
                    if (!name.isNullOrBlank() && !names.contains(name)) names += name
                }
                if (home.isBlank() && names.isNotEmpty()) home = names[0]
                if (away.isBlank() && names.size > 1) away = names[1]
                if (home.isBlank()) home = event.optString("name").ifBlank { league.league }
                if (away.isBlank()) away = league.league
            }

'''
    if inject_before not in s:
        raise SystemExit('event title anchor not found: refusing unsafe parser patch')
    s = s.replace(inject_before, inject + inject_before, 1)

SERVICE.write_text(s, encoding='utf-8')

t = SCREEN.read_text(encoding='utf-8')
t = re.sub(r'val leagueChoices = listOf\("ALL".*?\)', 'val leagueChoices = listOf("ALL") + SportsScheduleService.uiLeagueChoices', t, count=1, flags=re.S)
t = t.replace('SportsScheduleService.load()', 'SportsScheduleService.load(leagueFilter)', 1)
SCREEN.write_text(t, encoding='utf-8')

print('Expanded schedule registry and made all supported league chips reachable')
