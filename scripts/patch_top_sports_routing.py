from pathlib import Path

MOBILE = Path("app/src/main/java/com/xsportsx/app/FuturisticSports.kt")
MAIN = Path("app/src/main/java/com/xsportsx/app/MainActivityFuture.kt")
TV = Path("app/src/main/java/com/xsportsx/app/TvHome.kt")

# Mobile: Top Sports cards select an exact league and open the filtered schedule.
text = MOBILE.read_text()
text = text.replace(
    'fun FuturisticHome(onConnect: () -> Unit = {}, onNetwork: (XNetwork) -> Unit = {}) {',
    'fun FuturisticHome(onConnect: () -> Unit = {}, onNetwork: (XNetwork) -> Unit = {}, onSportLeague: (String) -> Unit = {}) {'
)
text = text.replace(
    'else -> MobileHomeContent(sourceConfigured, onConnect, onNetwork) }',
    'else -> MobileHomeContent(sourceConfigured, onConnect, onNetwork, onSportLeague) }'
)
text = text.replace(
    'private fun MobileHomeContent(sourceConfigured: Boolean, onConnect: () -> Unit, onNetwork: (XNetwork) -> Unit) {',
    'private fun MobileHomeContent(sourceConfigured: Boolean, onConnect: () -> Unit, onNetwork: (XNetwork) -> Unit, onSportLeague: (String) -> Unit) {'
)
text = text.replace(
    'SportBadgeCard(sport) { onConnect() }',
    'SportBadgeCard(sport) { onSportLeague(SportsScheduleService.canonicalLeagueFor(sport.name)) }'
)
MOBILE.write_text(text)

# Mobile host: remember the selected league and open SportsScheduleScreen with it.
text = MAIN.read_text()
text = text.replace(
    'var liveFilter by remember { mutableStateOf<String?>(null) }\n            var selectedEvent',
    'var liveFilter by remember { mutableStateOf<String?>(null) }\n            var selectedScheduleLeague by remember { mutableStateOf("ALL") }\n            var selectedEvent'
)
text = text.replace(
    'schedules -> SportsScheduleScreen(onBack = { schedules = false },',
    'schedules -> SportsScheduleScreen(initialLeague = selectedScheduleLeague, onBack = { schedules = false },'
)
old = 'FuturisticHome(onConnect = { if (connected) schedules = true else connectSource = true }, onNetwork = { network -> selectedEvent = null; liveFilter = network.name })'
new = 'FuturisticHome(onConnect = { if (connected) schedules = true else connectSource = true }, onNetwork = { network -> selectedEvent = null; liveFilter = network.name }, onSportLeague = { league -> selectedScheduleLeague = SportsScheduleService.canonicalLeagueFor(league); schedules = true })'
if old not in text:
    raise SystemExit("Mobile FuturisticHome host call not found")
text = text.replace(old, new, 1)
MAIN.write_text(text)

# TV: keep Top Sports inside the TV UI and select the exact league tab. Do not
# send a sport click through the generic network/live-channel callback.
text = TV.read_text()
old = 'TvSportRow(tvSports,onNetwork)'
new = 'TvSportRow(tvSports){ sport -> selectedNav = SportsScheduleService.canonicalLeagueFor(sport) }'
if old not in text:
    raise SystemExit("TV Top Sports row call not found")
text = text.replace(old, new, 1)
old_case = '"NFL","NCAA FB","NBA","WNBA","NCAA BB","MLB","NHL","SOCCER","F1","UFC","BOXING"->{TvSection(selectedNav,if(liveGames.any{it.league==selectedNav})"LIVE FEED" else "UPCOMING + LIVE");val live=liveGames.filter{it.league==selectedNav};val upcoming=upcomingGames.filter{it.league==selectedNav};if(live.isNotEmpty())TvGameRow(live,onNetwork);if(upcoming.isNotEmpty()){Spacer(Modifier.height(14.dp));TvSection("UPCOMING $selectedNav","SCHEDULED");TvGameRow(upcoming,onNetwork)};if(live.isEmpty()&&upcoming.isEmpty())TvLiveEmpty(loadingSchedule)}'
new_case = '"NFL","NCAA FB","NBA","WNBA","NCAA BB","MLB","NHL","UFC","BOXING","RUGBY","VOLLEYBALL","LACROSSE","WRESTLING","MOTOGP","WRC","WEC","IMSA","FORMULA E","MXGP","MONSTER JAM","ESPORTS","ACTION SPORTS","F1","NASCAR","INDYCAR"->{TvSection(selectedNav,if(liveGames.any{it.league==selectedNav})"LIVE FEED" else "UPCOMING + LIVE");val live=liveGames.filter{it.league==selectedNav};val upcoming=upcomingGames.filter{it.league==selectedNav};if(live.isNotEmpty())TvGameRow(live,onNetwork);if(upcoming.isNotEmpty()){Spacer(Modifier.height(14.dp));TvSection("UPCOMING $selectedNav","SCHEDULED");TvGameRow(upcoming,onNetwork)};if(live.isEmpty()&&upcoming.isEmpty())TvLiveEmpty(loadingSchedule)}'
if old_case in text:
    text = text.replace(old_case, new_case, 1)
TV.write_text(text)
print("Top Sports cards route to exact league schedules on mobile and TV")
