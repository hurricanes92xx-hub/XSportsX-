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

# patch_favorites_feed.py is also used by release/QA builds. It is now
# idempotent: only invoke it when the legacy FavoritesCenter block remains.
# If the feed is already patched, validate its marker instead of failing.
favorites_feed = Path("scripts/patch_favorites_feed.py")
current = source.read_text(encoding="utf-8")
legacy_loading = '''    LaunchedEffect(selected){
        loading=true
        events=runCatching{SportsScheduleService.load()}.getOrDefault(emptyList())
        news=loadFavoriteNews(selected.take(6))
        loading=false
        if(active==null||active !in selected)active=selected.firstOrNull()
    }'''
if legacy_loading in current:
    subprocess.run(["python3", str(favorites_feed)], check=True)
else:
    if "loadFavoriteFeed(snapshot)" not in current or "data class FavoriteFeed" not in current:
        raise SystemExit("Favorites feed is neither legacy nor patched; refusing unsafe rewrite")

# Add NCAA Volleyball to the existing Mobile top sport carousel. TV is patched
# after the general sports-badge patch so the two patchers remain order-safe.
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

print("College Favorites + NCAA volleyball mobile badge/feed classification applied")
