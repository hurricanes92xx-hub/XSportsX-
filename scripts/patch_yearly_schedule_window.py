#!/usr/bin/env python3
from pathlib import Path
import re

SERVICE = Path("app/src/main/java/com/xsportsx/app/SportsScheduleService.kt")
SCREEN = Path("app/src/main/java/com/xsportsx/app/SportsScheduleScreen.kt")

s = SERVICE.read_text(encoding="utf-8")

# Keep this patch idempotent. Earlier versions used over-escaped regexes and
# required an exact marker that other schedule patches could change.
s = re.sub(r"(const\s+val\s+DAYS_AHEAD\s*=\s*)\d+L?", r"\g<1>30L", s, count=1)
if "const val DAYS_AHEAD" not in s:
    s = s.replace("object SportsScheduleService {", "object SportsScheduleService {\n    private const val DAYS_AHEAD = 30L", 1)

# The service registry is already authoritative on current branches. Only
# restore the registry when a legacy build has actually lost it.
required = [
    'ScheduleLeague("MLS"',
    'ScheduleLeague("EPL"',
    'ScheduleLeague("NCAA WOMEN SOCCER"',
    'ScheduleLeague("NCAA WOMEN HOCKEY"',
    'ScheduleLeague("NCAA WBB"',
    'ScheduleLeague("NCAA VB"'
]

if not all(token in s for token in required):
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
        ScheduleLeague("NWSL", "Soccer", "soccer/usa.nwsl", "https://www.nwslsoccer.com/")
    )'''
    m = re.search(r"(?ms)^    private val leagues = listOf\(.*?^    \)\n\n    fun normalizeLeague", s)
    if not m:
        raise SystemExit("schedule league registry not found: refusing unsafe rewrite")
    s = s[:m.start()] + registry + "\n\n    fun normalizeLeague" + s[m.end():]

# Ensure the important aliases exist without depending on a fragile marker.
aliases = {
    '"NCAA WOMEN\'S BASKETBALL", "NCAA WOMENS BASKETBALL" -> "NCAA WBB"': 'NCAA WBB alias',
    '"NATIONAL WOMEN\'S SOCCER LEAGUE" -> "NWSL"': 'NWSL alias',
    '"NCAA WOMEN\'S SOCCER" -> "NCAA WOMEN SOCCER"': 'NCAA women soccer alias',
    '"COLLEGE WOMEN\'S HOCKEY" -> "NCAA WOMEN HOCKEY"': 'NCAA women hockey alias'
}
if "else -> label.trim().uppercase()" in s:
    missing = [line for line in aliases if line not in s]
    if missing:
        block = "\n".join("        " + line for line in missing) + "\n"
        s = s.replace("        else -> label.trim().uppercase()", block + "        else -> label.trim().uppercase()", 1)
SERVICE.write_text(s, encoding="utf-8")

# Keep UI choices synchronized with the service registry.
t = SCREEN.read_text(encoding="utf-8")
t = re.sub(r"val leagueChoices = listOf\(.*?\)", 'val leagueChoices = listOf("ALL") + SportsScheduleService.uiLeagueChoices', t, count=1, flags=re.S)
SCREEN.write_text(t, encoding="utf-8")
print("Schedule registry patch applied idempotently")
