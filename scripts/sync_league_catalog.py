from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

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
        raise SystemExit(f"Missing marker: {start}")
    b = text.find(end, a)
    if b < 0:
        raise SystemExit(f"Missing end marker: {end}")
    return text[:a] + replacement + text[b:]


# Mobile catalog remains generated from the canonical league list.
# TV no longer has a second schedule catalog: TvHomeUltimate derives its
# sports rail from SportsScheduleService.uiLeagueChoices.
mobile = ROOT / "app/src/main/java/com/xsportsx/app/FuturisticSports.kt"
text = mobile.read_text()
mobile_items = ",\n".join(f'    SportVisual("{name}", "{icon}", "")' for name, icon, _, _ in LEAGUES)
text = replace_between(
    text,
    "private val sports = listOf(",
    "@Composable private fun SportGlyph",
    f"private val sports = listOf(\n{mobile_items}\n)\n\n",
)
mobile.write_text(text)
print(f"Synchronized {len(LEAGUES)} canonical leagues into the Mobile catalog; TV derives its catalog from SportsScheduleService.")
