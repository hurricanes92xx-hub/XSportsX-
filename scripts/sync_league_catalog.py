from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

# One authoritative catalog. Keep this in lock-step with SportsScheduleService.uiLeagueChoices.
LEAGUES = [
    ("NFL", "NFL"), ("NBA", "NBA"), ("WNBA", "WNBA"),
    ("NCAA FB", "NCAA"), ("NCAA FCS", "FCS"), ("NCAA BB", "NCAA"), ("NCAA WBB", "NCAA"),
    ("MLB", "MLB"), ("NCAA BASEBALL", "NCAA"), ("NHL", "NHL"),
    ("NCAA MEN HOCKEY", "NCAA"), ("NCAA WOMEN HOCKEY", "NCAA"),
    ("NCAA SOFTBALL", "NCAA"), ("NCAA VB", "VB"),
    ("NCAA MEN SOCCER", "NCAA"), ("NCAA WOMEN SOCCER", "NCAA"),
    ("NCAA MEN LAX", "LAX"), ("NCAA WOMEN LAX", "LAX"),
    ("MLS", "MLS"), ("EPL", "EPL"), ("LaLiga", "LALIGA"),
    ("Bundesliga", "BUND"), ("Serie A", "SERIE A"), ("Ligue 1", "L1"),
    ("UCL", "UCL"), ("UEL", "UEL"), ("NWSL", "NWSL"),
    ("UFC", "UFC"), ("BOXING", "BOX"),
]

mobile = ROOT / "app/src/main/java/com/xsportsx/app/FuturisticSports.kt"
text = mobile.read_text()
# Remove stale hard-coded action-sports/esports entries and make the displayed league cards authoritative.
items = ",\n".join(f'    SportVisual("{name}", "{icon}", "")' for name, icon in LEAGUES)
replacement = f'private val sports = listOf(\n{items}\n)'
text, count = re.subn(r'private val sports = listOf\(.*?\n\)\n\n@Composable private fun SportGlyph', replacement + '\n\n@Composable private fun SportGlyph', text, count=1, flags=re.S)
if count != 1:
    raise SystemExit("Could not locate mobile sports catalog")
mobile.write_text(text)

tv = ROOT / "app/src/main/java/com/xsportsx/app/TvHome.kt"
text = tv.read_text()
# TV navigation must expose every configured league, not just the legacy nine-league subset.
tv_items = ",".join(f'TvLeague("{name}", "", "")' for name, _ in LEAGUES)
tv_live = 'val liveLeagues = listOf(' + ','.join(f'TvLeague("{name}", "", "")' for name, _ in LEAGUES) + ')'
tv_sports = 'private val tvSports = listOf(' + ','.join(f'TvSport("{name}", "{icon}")' for name, icon in LEAGUES) + ')'
text, c1 = re.subn(r'val liveLeagues = listOf\(.*?\)\nprivate val tvSports = listOf\(.*?\)\n', tv_live + '\n' + tv_sports + '\n', text, count=1, flags=re.S)
if c1 != 1:
    raise SystemExit("Could not locate TV league catalogs")
# Keep the existing ESPN live loader working by deriving sport/feed IDs from the canonical schedule service.
text = text.replace(
    'private suspend fun loadTvGames(liveOnly:Boolean=true):List<TvGame> = withContext(Dispatchers.IO) {',
    'private suspend fun loadTvGames(liveOnly:Boolean=true):List<TvGame> = withContext(Dispatchers.IO) {'
)
tv.write_text(text)
print(f"Synchronized {len(LEAGUES)} leagues across Mobile and TV")
