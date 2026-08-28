#!/usr/bin/env python3
from pathlib import Path
import re

SERVICE = Path("app/src/main/java/com/xsportsx/app/SportsScheduleService.kt")
SCREEN = Path("app/src/main/java/com/xsportsx/app/SportsScheduleScreen.kt")

s = SERVICE.read_text(encoding="utf-8")
s = re.sub(r"(const\\s+val\\s+DAYS_AHEAD\\s*=\\s*)\\d+L?", r"\\g<1>30L", s, count=1)
if "const val DAYS_AHEAD" not in s:
    s = s.replace("object SportsScheduleService {", "object SportsScheduleService {\n    private const val DAYS_AHEAD = 30L", 1)

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
        ScheduleLeague("NCAA SOFTBALL", "Softball", "softball/college-softball", "https://www.ncaa.com/sports/softball"),
        ScheduleLeague("NCAA VB", "Volleyball", "volleyball/womens-college-volleyball", "https://www.ncaa.com/sports/volleyball-women/d1"),
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

m = re.search(r"(?ms)^    private val leagues = listOf\\(.*?^    \\)\\n\\n    fun normalizeLeague", s)
if not m:
    raise SystemExit("schedule league registry not found: refusing unsafe rewrite")
s = s[:m.start()] + registry + "\n\n    fun normalizeLeague" + s[m.end():]

# Add aliases immediately before the catch-all instead of relying on a fragile old marker.
aliases = '''        "WNBA" -> "WNBA"
        "NCAA WOMEN'S BASKETBALL", "NCAA WOMENS BASKETBALL" -> "NCAA WBB"
        "NATIONAL WOMEN'S SOCCER LEAGUE" -> "NWSL"
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
    marker = '        else -> label.trim().uppercase()'
    if marker not in s:
        raise SystemExit("league normalization fallback not found: refusing unsafe rewrite")
    s = s.replace(marker, aliases + marker, 1)
SERVICE.write_text(s, encoding="utf-8")

# Keep the schedule UI synchronized with the authoritative service registry.
t = SCREEN.read_text(encoding="utf-8")
t = re.sub(r'val leagueChoices = listOf\\(.*?\\)', 'val leagueChoices = listOf("ALL") + SportsScheduleService.uiLeagueChoices', t, count=1, flags=re.S)
t = t.replace('SportsScheduleService.load()', 'SportsScheduleService.load()', 1)
SCREEN.write_text(t, encoding="utf-8")
print("Expanded schedule registry safely and made the UI choices authoritative")
