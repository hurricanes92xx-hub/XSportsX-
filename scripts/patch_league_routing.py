from pathlib import Path
import re

path = Path("app/src/main/java/com/xsportsx/app/TvHome.kt")
text = path.read_text()

# patch_sports_badges.py upgrades TvSport/TvNetwork to include logoUrl before
# this script runs. Replace the complete catalog so the UI always has one
# authoritative league list.
old_lists = re.compile(r"val liveLeagues = listOf\([^\n]+\)\nprivate val tvSports = listOf\([^\n]+\)\nprivate val tvNetworks = listOf\([^\n]+\)")
new_lists = """val liveLeagues = listOf(
    TvLeague("NFL","football","nfl"),
    TvLeague("NCAA FB","football","college-football"),
    TvLeague("NBA","basketball","nba"),
    TvLeague("WNBA","basketball","wnba"),
    TvLeague("NCAA BB","basketball","mens-college-basketball"),
    TvLeague("MLB","baseball","mlb"),
    TvLeague("NHL","hockey","nhl"),
    TvLeague("SOCCER","soccer","all"),
    TvLeague("F1","racing","f1"),
    TvLeague("UFC","mma","ufc"),
    TvLeague("BOXING","boxing","boxing")
)
private val tvSports = listOf(
    TvSport("NFL","NFL","https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png"),
    TvSport("NCAA FB","NCAA","https://a.espncdn.com/i/teamlogos/leagues/500/ncaaf.png"),
    TvSport("NBA","NBA","https://a.espncdn.com/i/teamlogos/leagues/500/nba.png"),
    TvSport("NCAA BB","NCAA","https://a.espncdn.com/i/teamlogos/leagues/500/ncaab.png"),
    TvSport("MLB","MLB","https://a.espncdn.com/i/teamlogos/leagues/500/mlb.png"),
    TvSport("NHL","NHL","https://a.espncdn.com/i/teamlogos/leagues/500/nhl.png"),
    TvSport("SOCCER","⚽",""),
    TvSport("F1","F1",""), TvSport("UFC","UFC",""), TvSport("BOXING","BOX","")
)
private val tvNetworks = listOf(
    TvNetwork("ESPN","ESPN",""), TvNetwork("ESPN2","ESPN2",""), TvNetwork("ESPNU","ESPNU",""),
    TvNetwork("NFL NETWORK","NFL",""), TvNetwork("FS1","FS1",""), TvNetwork("CBS SPORTS","CBS",""),
    TvNetwork("SEC NETWORK","SEC",""), TvNetwork("ACC NETWORK","ACC",""),
    TvNetwork("BIG TEN NETWORK","B1G",""), TvNetwork("ESPN+","ESPN+","")
)"""
text, count = old_lists.subn(new_lists, text, count=1)
if count != 1: raise SystemExit("league list block not found")

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

# Never show a blank tile when a remote badge is absent. Soccer intentionally
# uses the local ball mark so the soccer hub has zero remote-logo dependency.
badge_re = re.compile(r'@Composable private fun TvBadgeTile\(.*?\n@Composable private fun TvNetworkTile', re.S)
badge_block = '''@Composable private fun TvBadgeTile(sport:TvSport,onNetwork:(String)->Unit){
    var focused by remember{mutableStateOf(false)}
    Column(Modifier.width(142.dp).height(118.dp).clip(RoundedCornerShape(16.dp)).background(TvPanel).border(1.dp,TvBlue.copy(alpha=if(focused)1f else .25f),RoundedCornerShape(16.dp)).onFocusChanged{focused=it.isFocused}.focusable().clickable{onNetwork(sport.name)}.padding(10.dp),horizontalAlignment=Alignment.CenterHorizontally){
        Box(Modifier.weight(1f).fillMaxWidth(),contentAlignment=Alignment.Center){
            if(sport.logoUrl.isNotBlank()) AsyncImage(model=sport.logoUrl,contentDescription=sport.name,modifier=Modifier.size(70.dp),contentScale=ContentScale.Fit)
            else Text(sport.glyph,color=Color.White,fontSize=28.sp,fontWeight=FontWeight.Black)
        }
        Text(sport.name,color=Color.White,fontSize=10.sp,fontWeight=FontWeight.Black,maxLines=1,overflow=TextOverflow.Ellipsis)
    }
}
@Composable private fun TvNetworkTile'''
text, count = badge_re.subn(badge_block, text, count=1)
if count != 1: raise SystemExit("TV badge tile block not found")

net_re = re.compile(r'@Composable private fun TvNetworkTile\(.*?\n@Composable private fun TvTile', re.S)
net_block = '''@Composable private fun TvNetworkTile(network:TvNetwork,onNetwork:(String)->Unit){
    var focused by remember{mutableStateOf(false)}
    Column(Modifier.width(142.dp).height(96.dp).clip(RoundedCornerShape(16.dp)).background(TvPanel).border(1.dp,TvRed.copy(alpha=if(focused)1f else .25f),RoundedCornerShape(16.dp)).onFocusChanged{focused=it.isFocused}.focusable().clickable{onNetwork(network.name)}.padding(10.dp),horizontalAlignment=Alignment.CenterHorizontally){
        if(network.logoUrl.isNotBlank()) AsyncImage(model=network.logoUrl,contentDescription=network.name,modifier=Modifier.size(42.dp),contentScale=ContentScale.Fit) else Text(network.mark,color=Color.White,fontSize=13.sp,fontWeight=FontWeight.Black)
        Spacer(Modifier.height(6.dp))
        Text(network.name,color=Color.White,fontSize=9.sp,fontWeight=FontWeight.Bold,maxLines=1,overflow=TextOverflow.Ellipsis)
    }
}
@Composable private fun TvTile'''
text, count = net_re.subn(net_block, text, count=1)
if count != 1: raise SystemExit("TV network tile block not found")

path.write_text(text)
print("League routing locked to SportsScheduleService; all soccer grouped under SOCCER; live/upcoming separated")
