from pathlib import Path
import re

source = Path("app/src/main/java/com/xsportsx/app/TeamFavorites.kt")
text = source.read_text(encoding="utf-8")

# TeamFavorites owns the picker list. Inject the college catalog exactly once,
# using a regex so whitespace/newline formatting cannot make the patch silently fail.
if "addAll(collegeFavoriteTeams())" not in text:
    text, count = re.subn(
        r"(private\s+val\s+favoriteTeams\s*=\s*buildList\s*\{)",
        r"\1\n    addAll(collegeFavoriteTeams())",
        text,
        count=1,
    )
    if count != 1:
        raise SystemExit("favoriteTeams marker not found")

# Add college ESPN paths to the existing team-news mapping. The mapping is on
# the same source line in the current compact Kotlin file, so do not depend on
# a literal newline or exact formatting.
league_pattern = r"val league=when\(team\.league\)\{.*?\}"
league_replacement = 'val league=when(team.league){"NFL"->"football/nfl";"NBA"->"basketball/nba";"MLB"->"baseball/mlb";"NHL"->"hockey/nhl";"NCAAF"->"football/college-football";"NCAAM"->"basketball/mens-college-basketball";"NCAAW"->"basketball/womens-college-basketball";"NCAAB"->"baseball/college-baseball";else->return emptyList()}'
text, count = re.subn(league_pattern, league_replacement, text, count=1)
if count != 1:
    raise SystemExit("favorite news league mapping not found")

# Hard validation: the shell workflow should never reach its greps with a
# partially applied patch.
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
