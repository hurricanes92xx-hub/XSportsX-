from pathlib import Path
import re

path = Path("app/src/main/java/com/xsportsx/app/TvHome.kt")
text = path.read_text()

# patch_sports_badges.py owns the league/network catalog and hardwired logo
# fields. Do not replace those lists here; this patch only owns schedule routing.
loader_re = re.compile(r"private fun dateRange\(\):String.*?\n\n@Composable fun TvHome", re.S)
loader = """private suspend fun loadTvGames():List<TvGame> = withContext(Dispatchers.IO) {
    runCatching { SportsScheduleService.load() }.getOrDefault(emptyList()).mapNotNull { event ->
        val start = runCatching { java.time.Instant.parse(event.startUtc).toEpochMilli() }.getOrDefault(0L)
        if (start == 0L) return@mapNotNull null
        val league = if (event.sport.equals("Soccer", true)) "SOCCER" else event.league.uppercase()
        TvGame(
            league = league,
            home = event.home.ifBlank { event.title.ifBlank { "TBD" } },
            away = event.away,
            homeLogo = event.homeLogo,
            awayLogo = event.awayLogo,
            score = if (event.isLive) "LIVE" else "—",
            status = event.status.ifBlank { if (event.isLive) "LIVE" else "UPCOMING" },
            network = event.broadcast.ifBlank { "TBD" },
            live = event.isLive,
            timestamp = start
        )
    }.distinctBy { listOf(it.league,it.home,it.away,it.timestamp / 60000L).joinToString("|") }
     .sortedWith(compareBy<TvGame> { !it.live }.thenBy { it.timestamp })
     .take(200)
}

@Composable fun TvHome"""
text, count = loader_re.subn(loader, text, count=1)
if count != 1: raise SystemExit("old schedule loader block not found")

old_state = """    var liveGames by remember{mutableStateOf<List<TvGame>>(emptyList())}
    var upcomingGames by remember{mutableStateOf<List<TvGame>>(emptyList())}
    var loadingLive by remember{mutableStateOf(true)}
    var loadingUpcoming by remember{mutableStateOf(false)}
    val scroll=rememberScrollState()
    LaunchedEffect(Unit){while(isActive){loadingLive=liveGames.isEmpty();liveGames=runCatching{loadTvGames(true)}.getOrDefault(emptyList());loadingLive=false;delay(60_000)}}
    LaunchedEffect(selectedNav){if(selectedNav=="UPCOMING"&&upcomingGames.isEmpty()){loadingUpcoming=true;upcomingGames=runCatching{loadTvGames(false)}.getOrDefault(emptyList());loadingUpcoming=false}}"""
new_state = """    var allGames by remember{mutableStateOf<List<TvGame>>(emptyList())}
    var loadingSchedule by remember{mutableStateOf(true)}
    val liveGames = allGames.filter { it.live }
    val upcomingGames = allGames.filter { !it.live && it.timestamp > System.currentTimeMillis() }
    val scroll=rememberScrollState()
    LaunchedEffect(Unit){
        while(isActive){
            loadingSchedule = allGames.isEmpty()
            allGames = loadTvGames()
            loadingSchedule = false
            delay(60_000)
        }
    }"""
if old_state not in text: raise SystemExit("TvHome state block not found")
text=text.replace(old_state,new_state,1)

old_case='"NFL","NCAA FB","NBA","WNBA","NCAA BB","MLB","NHL","MLS","EPL"->{TvSection(selectedNav,"LIVE FEED");val games=liveGames.filter{it.league==selectedNav};if(games.isNotEmpty())TvGameRow(games,onNetwork)else TvLiveEmpty(false)}'
new_case='"NFL","NCAA FB","NBA","WNBA","NCAA BB","MLB","NHL","SOCCER","F1","UFC","BOXING"->{TvSection(selectedNav,if(liveGames.any{it.league==selectedNav})"LIVE FEED" else "UPCOMING + LIVE");val live=liveGames.filter{it.league==selectedNav};val upcoming=upcomingGames.filter{it.league==selectedNav};if(live.isNotEmpty())TvGameRow(live,onNetwork);if(upcoming.isNotEmpty()){Spacer(Modifier.height(14.dp));TvSection("UPCOMING $selectedNav","SCHEDULED");TvGameRow(upcoming,onNetwork)};if(live.isEmpty()&&upcoming.isEmpty())TvLiveEmpty(loadingSchedule)}'
if old_case not in text: raise SystemExit("league UI case not found")
text=text.replace(old_case,new_case,1)

text=text.replace('TvSection("LIVE NOW",if(liveGames.isEmpty())"Waiting for live scores" else "${liveGames.size} LIVE")','TvSection("LIVE NOW",if(liveGames.isEmpty())"No games live right now" else "${liveGames.size} LIVE")',1)
text=text.replace('else TvLiveEmpty(loadingLive)','else TvLiveEmpty(loadingSchedule)',2)
text=text.replace('TvSection("UPCOMING",if(loadingUpcoming)"LOADING" else "${upcomingGames.size} EVENTS")','TvSection("UPCOMING",if(loadingSchedule)"LOADING" else "${upcomingGames.size} EVENTS")',1)
text=text.replace('else TvLiveEmpty(loadingUpcoming)','else TvLiveEmpty(loadingSchedule)',1)

path.write_text(text)
print("League routing fixed without overwriting hardwired sports/network catalog")