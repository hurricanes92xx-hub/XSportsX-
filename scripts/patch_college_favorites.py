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
league_replacement = 'val path=when(team.league){"NFL"->"football/nfl";"NBA"->"basketball/nba";"MLB"->"baseball/mlb";"NHL"->"hockey/nhl";"NCAAF"->"football/college-football";"NCAAM"->"basketball/mens-college-basketball";"NCAAW"->"basketball/womens-college-basketball";"NCAAB"->"baseball/college-baseball";"NCAAV"->"volleyball/womens-college-volleyball";else->return emptyList()}'
text, count = re.subn(league_pattern, league_replacement, text, count=1, flags=re.DOTALL)
if count != 1:
    raise SystemExit("favorite news path mapping not found")

required = [
    "addAll(collegeFavoriteTeams())",
    '"NCAAF"->"football/college-football"',
    '"NCAAM"->"basketball/mens-college-basketball"',
    '"NCAAW"->"basketball/womens-college-basketball"',
    '"NCAAB"->"baseball/college-baseball"',
    '"NCAAV"->"volleyball/womens-college-volleyball"',
    ":List<FavoriteTeam> =",
    ":List<FavoriteNews> =",
]
missing = [item for item in required if item not in text]
if missing:
    raise SystemExit("college favorites patch incomplete: " + ", ".join(missing))

source.write_text(text, encoding="utf-8")
subprocess.run(["python3", "scripts/patch_favorites_feed.py"], check=True)

# Keep college volleyball visible in the existing Home top sport carousel on both builds.
# Use the NCAA Volleyball wordmark rather than a generic volleyball/favicon icon.
NCAA_VB_LOGO = "https://commons.wikimedia.org/wiki/Special:Redirect/file/NCAA_Volleyball_wordmark_color.svg"

mobile = Path("app/src/main/java/com/xsportsx/app/FuturisticSports.kt")
if mobile.exists():
    m = mobile.read_text(encoding="utf-8")
    if 'SportVisual("NCAA VB"' not in m:
        marker = '    SportVisual("NCAA BB", "NCAA", "https://a.espncdn.com/i/teamlogos/leagues/500/ncaab.png"),'
        if marker not in m:
            raise SystemExit("NCAA BB mobile sport marker not found")
        m = m.replace(marker, marker + f'\n    SportVisual("NCAA VB", "NCAA", "{NCAA_VB_LOGO}"),', 1)
    mobile.write_text(m, encoding="utf-8")

# TV uses the same existing horizontal sport carousel and the same lightweight remote badge.
tv = Path("app/src/main/java/com/xsportsx/app/TvHome.kt")
if tv.exists():
    t = tv.read_text(encoding="utf-8")
    if 'TvSport("NCAA VB"' not in t:
        marker = '    TvSport("NCAA BB","NCAA","https://a.espncdn.com/i/teamlogos/leagues/500/ncaab.png"),'
        if marker not in t:
            raise SystemExit("NCAA BB TV sport marker not found")
        t = t.replace(marker, marker + f'\n    TvSport("NCAA VB","NCAA","{NCAA_VB_LOGO}"),', 1)
    tv.write_text(t, encoding="utf-8")

print("College Favorites + NCAA volleyball sport badge/feed classification applied")
