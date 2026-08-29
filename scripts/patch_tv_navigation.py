from pathlib import Path
import re

p = Path("app/src/main/java/com/xsportsx/app/TvHome.kt")
if not p.is_file():
    raise SystemExit(f"Missing TV source: {p}")

s = p.read_text(encoding="utf-8")

s = re.sub(r'private suspend fun loadTvGames\(liveOnly:Boolean=true\):List<TvGame>=', 'private suspend fun loadTvGames(liveOnly:Boolean=true): List<TvGame> =', s, count=1)
s = re.sub(r'private suspend fun loadTvGames\(liveOnly: Boolean = true\): List<TvGame>\s*=', 'private suspend fun loadTvGames(liveOnly: Boolean = true): List<TvGame> =', s, count=1)
s = s.replace('var tvModeEnabled by remember{mutableStateOf(false)};', '')
s = s.replace('TvTopBar(onSettings={selectedNav="SETTINGS"},tvModeEnabled=tvModeEnabled,onToggleTvMode={tvModeEnabled=!tvModeEnabled})', 'TvTopBar{selectedNav="SETTINGS"}')
s = s.replace('}}}}};HomeSportsTicker(Modifier.align(Alignment.BottomCenter).fillMaxWidth())}}', '}}}};HomeSportsTicker(Modifier.align(Alignment.BottomCenter).fillMaxWidth())}}', 1)

if len(re.findall(r'@Composable\s+private fun TvActionButton\s*\(', s)) > 1:
    raise SystemExit("Duplicate TvActionButton definitions detected; refusing to patch")

routing = r'''from pathlib import Path
import re

p = Path("app/src/main/java/com/xsportsx/app/TvHome.kt")
s = p.read_text(encoding="utf-8")

league_block = r"""val liveLeagues = listOf(
    TvLeague("NFL","football","nfl"), TvLeague("NCAA FB","football","college-football"),
    TvLeague("NBA","basketball","nba"), TvLeague("WNBA","basketball","wnba"),
    TvLeague("NCAA BB","basketball","mens-college-basketball"), TvLeague("MLB","baseball","mlb"),
    TvLeague("NHL","hockey","nhl"), TvLeague("SOCCER","soccer","all"),
    TvLeague("F1","racing","f1"), TvLeague("UFC","mma","ufc"), TvLeague("BOXING","boxing","boxing")
)"""
s = re.sub(r"val liveLeagues = listOf\(.*?\)\s*private val tvSports", league_block + "\nprivate val tvSports", s, count=1, flags=re.S)

loader = r"""private suspend fun loadTvGames(): List<TvGame> = withContext(Dispatchers.IO) {
    runCatching { SportsScheduleService.load() }.getOrDefault(emptyList()).mapNotNull { event ->
        val start = runCatching { java.time.Instant.parse(event.startUtc).toEpochMilli() }.getOrDefault(0L)
        if (start == 0L) return@mapNotNull null
        val league = if (event.sport.equals("Soccer", true)) "SOCCER" else event.league.uppercase()
        TvGame(league, event.home.ifBlank { event.title.ifBlank { "TBD" } }, event.away,
            event.homeLogo, event.awayLogo, if (event.isLive) "LIVE" else "—",
            event.status.ifBlank { if (event.isLive) "LIVE" else "UPCOMING" },
            event.broadcast.ifBlank { "TBD" }, event.isLive, start)
    }.distinctBy { listOf(it.league,it.home,it.away,it.timestamp / 60000L).joinToString("|") }
     .sortedWith(compareBy<TvGame> { !it.live }.thenBy { it.timestamp }).take(200)
}"""
s = re.sub(r"private fun dateRange\(\):String.*?\n\n@Composable fun TvHome", loader + "\n\n@Composable fun TvHome", s, count=1, flags=re.S)

new_state = r"""    var allGames by remember{mutableStateOf<List<TvGame>>(emptyList())}
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
start = s.find('    var liveGames by remember')
box = s.find('    Box(Modifier.fillMaxSize().background(TvBg))', start)
if start >= 0 and box >= 0:
    s = s[:start] + new_state + "\n" + s[box:]
else:
    raise SystemExit('TV schedule state block boundaries not found; refusing unsafe rewrite')

old_case = '"NFL","NCAA FB","NBA","WNBA","NCAA BB","MLB","NHL","MLS","EPL"->{TvSection(selectedNav,"LIVE FEED");val games=liveGames.filter{it.league==selectedNav};if(games.isNotEmpty())TvGameRow(games,onNetwork)else TvLiveEmpty(false)}'
new_case = '"NFL","NCAA FB","NBA","WNBA","NCAA BB","MLB","NHL","SOCCER","F1","UFC","BOXING"->{TvSection(selectedNav,if(liveGames.any{it.league==selectedNav})"LIVE FEED" else "UPCOMING + LIVE");val live=liveGames.filter{it.league==selectedNav};val upcoming=upcomingGames.filter{it.league==selectedNav};if(live.isNotEmpty())TvGameRow(live,onNetwork);if(upcoming.isNotEmpty()){Spacer(Modifier.height(14.dp));TvSection("UPCOMING $selectedNav","SCHEDULED");TvGameRow(upcoming,onNetwork)};if(live.isEmpty()&&upcoming.isEmpty())TvLiveEmpty(loadingSchedule)}'
s = s.replace(old_case, new_case, 1)
s = s.replace('TvSection("LIVE NOW",if(liveGames.isEmpty())"Waiting for live scores" else "${liveGames.size} LIVE")','TvSection("LIVE NOW",if(liveGames.isEmpty())"No games live right now" else "${liveGames.size} LIVE")',1)
s = s.replace('else TvLiveEmpty(loadingLive)','else TvLiveEmpty(loadingSchedule)')
s = s.replace('TvSection("UPCOMING",if(loadingUpcoming)"LOADING" else "${upcomingGames.size} EVENTS")','TvSection("UPCOMING",if(loadingSchedule)"LOADING" else "${upcomingGames.size} EVENTS")',1)
s = s.replace('else TvLiveEmpty(loadingUpcoming)','else TvLiveEmpty(loadingSchedule)')

p.write_text(s, encoding="utf-8")
print("League routing patch normalized for multiline catalogs")
'''
Path("scripts/patch_league_routing.py").write_text(routing, encoding="utf-8")

p.write_text(s, encoding="utf-8")
print("TV navigation patch applied safely")

mobile = Path("app/src/main/java/com/xsportsx/app/FuturisticSports.kt")
if mobile.is_file():
    ms = mobile.read_text(encoding="utf-8")
    ms = ms.replace('Text("LIVE", color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Black)', 'Text("LIVE NOW", color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Black)', 1)
    mobile.write_text(ms, encoding="utf-8")
    print("Mobile LIVE hero label normalized for deterministic navigation")

qr = Path("app/src/main/java/com/xsportsx/app/QrPairingScreen.kt")
if qr.is_file():
    qs = qr.read_text(encoding="utf-8")
    if 'import androidx.activity.compose.BackHandler' not in qs:
        qs = qs.replace('package com.xsportsx.app\n\n', 'package com.xsportsx.app\n\nimport androidx.activity.compose.BackHandler\n', 1)
    marker = '    var connected by remember { mutableStateOf(false) }\n'
    if marker in qs and 'BackHandler(enabled = true)' not in qs:
        qs = qs.replace(marker, marker + '\n    BackHandler(enabled = true) { onDone() }\n', 1)
    qr.write_text(qs, encoding="utf-8")
    print("TV QR cancellation back handling hardened")
