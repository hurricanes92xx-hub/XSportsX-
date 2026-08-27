from pathlib import Path

p = Path('app/src/main/java/com/xsportsx/app/SportsScheduleScreen.kt')
s = p.read_text()

old = 'val leagueChoices = listOf("ALL", "NFL", "NCAA FB", "NBA", "NCAA BB", "MLB", "NHL", "UFC", "BOXING")'
new = '''val leagueChoices = listOf(
        "ALL", "NFL", "NBA", "WNBA", "NCAA FB", "NCAA FCS", "NCAA BB", "NCAA WBB",
        "MLB", "NCAA BASEBALL", "NHL", "NCAA MEN HOCKEY", "NCAA WOMEN HOCKEY", "NCAA SOFTBALL",
        "NCAA VB", "NCAA MEN SOCCER", "NCAA WOMEN SOCCER", "NCAA MEN LAX", "NCAA WOMEN LAX", "NCAA WRESTLING",
        "MLS", "EPL", "LaLiga", "Bundesliga", "Serie A", "Ligue 1", "UCL", "UEL", "NWSL",
        "UFC", "BOXING", "RUGBY", "F1", "NASCAR", "INDYCAR"
    )'''
if old in s:
    s = s.replace(old, new, 1)

old_broadcast = 'Text(event.status.ifBlank { event.broadcast }.ifBlank { "EVENT" }, color = Color(0xFF7F8794), fontSize = 10.sp)'
new_broadcast = 'Text(event.broadcast.ifBlank { event.status }.ifBlank { "EVENT" }, color = Color(0xFF7F8794), fontSize = 10.sp)'
if old_broadcast in s:
    s = s.replace(old_broadcast, new_broadcast, 1)

required = [
    'TeamLogo(event.homeLogo, event.home.ifBlank { "HOME" }, event.league, 76.dp)',
    'TeamLogo(event.awayLogo, event.away.ifBlank { "AWAY" }, event.league, 76.dp)',
]
for marker in required:
    if marker not in s:
        raise SystemExit(f'Missing real team-logo binding: {marker}')

p.write_text(s)
print('College schedule filters and broadcast display patched; real event team logos preserved')
