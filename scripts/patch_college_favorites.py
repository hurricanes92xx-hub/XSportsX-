from pathlib import Path

source = Path("app/src/main/java/com/xsportsx/app/TeamFavorites.kt")
text = source.read_text(encoding="utf-8")

marker = "private val favoriteTeams=buildList{\n"
injection = marker + "    addAll(collegeFavoriteTeams())\n"
if "addAll(collegeFavoriteTeams())" not in text:
    if marker not in text:
        raise SystemExit("favoriteTeams marker not found")
    text = text.replace(marker, injection, 1)

old = 'val league=when(team.league){"NFL"->"football/nfl";"NBA"->"basketball/nba";"MLB"->"baseball/mlb";"NHL"->"hockey/nhl";else->return emptyList()}'
new = 'val league=when(team.league){"NFL"->"football/nfl";"NBA"->"basketball/nba";"MLB"->"baseball/mlb";"NHL"->"hockey/nhl";"NCAAF"->"football/college-football";"NCAAM"->"basketball/mens-college-basketball";"NCAAW"->"basketball/womens-college-basketball";"NCAAB"->"baseball/college-baseball";else->return emptyList()}'
if old in text:
    text = text.replace(old, new, 1)

source.write_text(text, encoding="utf-8")
print("College Favorites patch applied")
