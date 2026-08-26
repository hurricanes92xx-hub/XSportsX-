from pathlib import Path
import re
import subprocess

source = Path("app/src/main/java/com/xsportsx/app/TeamFavorites.kt")
text = source.read_text(encoding="utf-8")

if "addAll(collegeFavoriteTeams())" not in text:
    text, count = re.subn(
        r"(private\s+val\s+favoriteTeams\s*=\s*buildList\s*\{)",
        r"\1\n    addAll(collegeFavoriteTeams())",
        text,
        count=1,
    )
    if count != 1:
        raise SystemExit("favoriteTeams marker not found")

text = text.replace(":List<FavoriteTeam>=", ":List<FavoriteTeam> =")
text = text.replace(":List<FavoriteNews>=", ":List<FavoriteNews> =")

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
    ":List<FavoriteTeam> =",
    ":List<FavoriteNews> =",
]
missing = [item for item in required if item not in text]
if missing:
    raise SystemExit("college favorites patch incomplete: " + ", ".join(missing))

source.write_text(text, encoding="utf-8")
subprocess.run(["python3", "scripts/patch_favorites_feed.py"], check=True)
print("College Favorites + team-specific feed patches applied and verified")
