from pathlib import Path
import re

source = Path("app/src/main/java/com/xsportsx/app/TeamFavorites.kt")
text = source.read_text(encoding="utf-8")

# TeamFavorites owns the picker list. Inject the college catalog exactly once.
if "addAll(collegeFavoriteTeams())" not in text:
    text, count = re.subn(
        r"(private\s+val\s+favoriteTeams\s*=\s*buildList\s*\{)",
        r"\1\n    addAll(collegeFavoriteTeams())",
        text,
        count=1,
    )
    if count != 1:
        raise SystemExit("favoriteTeams marker not found")

# fetchNews uses a compact `val path=when(team.league)` mapping. Replace the
# complete expression rather than depending on whitespace/newline formatting.
league_pattern = r"val path=when\(team\.league\)\{.*?\}"
league_replacement = 'val path=when(team.league){"NFL"->"football/nfl";"NBA"->"basketball/nba";"MLB"->"baseball/mlb";"NHL"->"hockey/nhl";"NCAAF"->"football/college-football";"NCAAM"->"basketball/mens-college-basketball";"NCAAW"->"basketball/womens-college-basketball";"NCAAB"->"baseball/college-baseball";else->return emptyList()}'
text, count = re.subn(league_pattern, league_replacement, text, count=1, flags=re.DOTALL)
if count != 1:
    raise SystemExit("favorite news path mapping not found")

required = [
    "addAll(collegeFavoriteTeams())",
    '"NCAAF"->"football/college-football"',
    '"NCAAM"->"basketball/mens-college-basketball"',
    '"NCAAW"->"basketball/womens-college-basketball"',
    '"NCAAB"->"baseball/college-baseball"',
]
missing = [item for item in required if item not in text]
if missing:
    raise SystemExit("college favorites patch incomplete: " + ", ".join(missing))

source.write_text(text, encoding="utf-8")
print("College Favorites patch applied and verified")
