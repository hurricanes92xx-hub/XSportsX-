from pathlib import Path
import re

source = Path("app/src/main/java/com/xsportsx/app/TeamFavorites.kt")
text = source.read_text(encoding="utf-8")

marker = "private val favoriteTeams=buildList{\n"
injection = marker + "    addAll(collegeFavoriteTeams())\n"
if "addAll(collegeFavoriteTeams())" not in text:
    if marker not in text:
        raise SystemExit("favoriteTeams marker not found")
    text = text.replace(marker, injection, 1)

# CollegeFavorites.kt owns the team catalog. Keep the news endpoint mapping
# compatible with formatting changes in TeamFavorites.kt.
league_pattern = r'val league=when\(team\.league\)\{[^\n]*\}'
league_replacement = 'val league=when(team.league){"NFL"->"football/nfl";"NBA"->"basketball/nba";"MLB"->"baseball/mlb";"NHL"->"hockey/nhl";"NCAAF"->"football/college-football";"NCAAM"->"basketball/mens-college-basketball";"NCAAW"->"basketball/womens-college-basketball";"NCAAB"->"baseball/college-baseball";else->return emptyList()}'
text, count = re.subn(league_pattern, league_replacement, text, count=1)
if count != 1:
    # The favorites UI is still build-safe if the news mapper is absent;
    # do not block the APK build over an optional news enhancement.
    print("College news mapper not present; leaving existing mapper unchanged")

source.write_text(text, encoding="utf-8")
print("College Favorites patch applied")
