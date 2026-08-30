from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

# Authoritative catalog: name, display glyph, ESPN sport, ESPN league id.
LEAGUES = [
    ("NFL", "NFL", "football", "nfl"), ("NBA", "NBA", "basketball", "nba"), ("WNBA", "WNBA", "basketball", "wnba"),
    ("NCAA FB", "NCAA", "football", "college-football"), ("NCAA FCS", "FCS", "football", "college-football"),
    ("NCAA BB", "NCAA", "basketball", "mens-college-basketball"), ("NCAA WBB", "NCAA", "basketball", "womens-college-basketball"),
    ("MLB", "MLB", "baseball", "mlb"), ("NCAA BASEBALL", "NCAA", "baseball", "college-baseball"),
    ("NHL", "NHL", "hockey", "nhl"), ("NCAA MEN HOCKEY", "NCAA", "hockey", "mens-college-hockey"),
    ("NCAA WOMEN HOCKEY", "NCAA", "hockey", "womens-college-hockey"), ("NCAA SOFTBALL", "NCAA", "softball", "college-softball"),
    ("NCAA VB", "VB", "volleyball", "womens-college-volleyball"), ("NCAA MEN SOCCER", "NCAA", "soccer", "usa.ncaa.m.1"),
    ("NCAA WOMEN SOCCER", "NCAA", "soccer", "usa.ncaa.w.1"), ("NCAA MEN LAX", "LAX", "lacrosse", "mens-college-lacrosse"),
    ("NCAA WOMEN LAX", "LAX", "lacrosse", "womens-college-lacrosse"), ("MLS", "MLS", "soccer", "usa.1"),
    ("EPL", "EPL", "soccer", "eng.1"), ("LaLiga", "LALIGA", "soccer", "esp.1"), ("Bundesliga", "BUND", "soccer", "ger.1"),
    ("Serie A", "SERIE A", "soccer", "ita.1"), ("Ligue 1", "L1", "soccer", "fra.1"), ("UCL", "UCL", "soccer", "uefa.champions"),
    ("UEL", "UEL", "soccer", "uefa.europa"), ("NWSL", "NWSL", "soccer", "usa.nwsl"), ("UFC", "UFC", "mma", "ufc"),
    ("BOXING", "BOX", "boxing", "boxing"),
]

mobile = ROOT / "app/src/main/java/com/xsportsx/app/FuturisticSports.kt"
text = mobile.read_text()
items = ",\n".join(f'    SportVisual("{name}", "{icon}", "")' for name, icon, _, _ in LEAGUES)
replacement = f'private val sports = listOf(\n{items}\n)'
text, count = re.subn(r'private val sports = listOf\(.*?\n\)\n\n@Composable private fun SportGlyph', replacement + '\n\n@Composable private fun SportGlyph', text, count=1, flags=re.S)
if count != 1:
    raise SystemExit("Could not locate mobile sports catalog")
mobile.write_text(text)

tv = ROOT / "app/src/main/java/com/xsportsx/app/TvHome.kt"
text = tv.read_text()
tv_live = 'val liveLeagues = listOf(' + ','.join(f'TvLeague("{name}", "{sport}", "{league_id}")' for name, _, sport, league_id in LEAGUES) + ')'
tv_sports = 'private val tvSports = listOf(' + ','.join(f'TvSport("{name}", "{icon}")' for name, icon, _, _ in LEAGUES) + ')'
text, count = re.subn(r'val liveLeagues = listOf\(.*?\)\nprivate val tvSports = listOf\(.*?\)\n', tv_live + '\n' + tv_sports + '\n', text, count=1, flags=re.S)
if count != 1:
    raise SystemExit("Could not locate TV league catalogs")
# Every league in the catalog must be selectable. Keep UFC/BOXING on their event UI,
# while all other leagues use the same live/upcoming game rows.
old = '"NFL","NCAA FB","NBA","WNBA","NCAA BB","MLB","NHL","MLS","EPL"->{TvSection(selectedNav,"LIVE FEED");val games=liveGames.filter{it.league==selectedNav};if(games.isNotEmpty())TvGameRow(games,onNetwork)else TvLiveEmpty(false)}'
new = 'else->{TvSection(selectedNav,"LIVE + UPCOMING");val games=(liveGames+upcomingGames).filter{it.league==selectedNav}.distinctBy{it.league+it.home+it.away+it.timestamp};if(games.isNotEmpty())TvGameRow(games,onNetwork)else TvEmpty("No ${selectedNav} events in the current schedule window")}'
if old not in text:
    raise SystemExit("Could not locate TV league routing")
text = text.replace(old, new)
# Remove the old UFC/BOXING special branches; the generic route now covers them too.
text = re.sub(r'\n\s*"UFC","BOXING"->\{TvSection\(selectedNav,"EVENT FEED"\);TvSportRow\(tvSports\.filter\{it\.name==selectedNav\},onNetwork\);Spacer\(Modifier\.height\(14\.dp\)\);TvEmpty\("Select \$\{selectedNav\} to browse available events"\)\}', '', text)
tv.write_text(text)
print(f"Synchronized {len(LEAGUES)} leagues across Mobile and TV")
