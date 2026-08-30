from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

# Authoritative catalog: display name, glyph, ESPN sport, ESPN league id.
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


def replace_between(text: str, start: str, end: str, replacement: str) -> str:
    a = text.find(start)
    if a < 0:
        raise SystemExit(f"Missing catalog marker: {start}")
    b = text.find(end, a)
    if b < 0:
        raise SystemExit(f"Missing catalog end marker: {end}")
    return text[:a] + replacement + text[b:]


# Mobile: replace only the catalog block; never depend on formatting inside it.
mobile = ROOT / "app/src/main/java/com/xsportsx/app/FuturisticSports.kt"
text = mobile.read_text()
mobile_items = ",\n".join(f'    SportVisual("{name}", "{icon}", "")' for name, icon, _, _ in LEAGUES)
mobile_block = f"private val sports = listOf(\n{mobile_items}\n)\n\n"
text = replace_between(text, "private val sports = listOf(", "@Composable private fun SportGlyph", mobile_block)
mobile.write_text(text)

# TV: replace both catalogs without touching the rest of the UI.
tv = ROOT / "app/src/main/java/com/xsportsx/app/TvHome.kt"
text = tv.read_text()
tv_live = "val liveLeagues = listOf(" + ",".join(
    f'TvLeague("{name}", "{sport}", "{league_id}")' for name, _, sport, league_id in LEAGUES
) + ")\n"
tv_sports = "private val tvSports = listOf(" + ",".join(
    f'TvSport("{name}", "{icon}")' for name, icon, _, _ in LEAGUES
) + ")\n"
text = replace_between(text, "val liveLeagues = listOf(", "private val tvNetworks", tv_live + tv_sports)

# Replace the legacy fixed nine-league + special-event routing with one generic route.
legacy = re.compile(
    r'\n\s*"NFL","NCAA FB","NBA","WNBA","NCAA BB","MLB","NHL","MLS","EPL"->\{.*?\}\n\s*"UFC","BOXING"->\{.*?\}',
    re.S,
)
generic = '''\n                    else->{\n                        TvSection(selectedNav,"LIVE + UPCOMING")\n                        val games=(liveGames+upcomingGames)\n                            .filter{it.league==selectedNav}\n                            .distinctBy{it.league+it.home+it.away+it.timestamp}\n                        if(games.isNotEmpty()) TvGameRow(games,onNetwork)\n                        else TvEmpty("No ${selectedNav} events in the current schedule window")\n                    }'''
text, count = legacy.subn(generic, text, count=1)
if count != 1:
    raise SystemExit("Missing legacy TV league routing block")
tv.write_text(text)

print(f"Synchronized {len(LEAGUES)} leagues across Mobile and TV")
