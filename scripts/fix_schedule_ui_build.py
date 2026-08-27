#!/usr/bin/env python3
from pathlib import Path
import subprocess

SCREEN = Path('app/src/main/java/com/xsportsx/app/SportsScheduleScreen.kt')
s = SCREEN.read_text(encoding='utf-8')

# Rebuild only the stable top-level screen function. This prevents any
# text-based schedule catalog patch from consuming surrounding Compose UI.
start_marker = '@Composable\nfun SportsScheduleScreen('
end_marker = '@Composable\nprivate fun ScheduleEventCard'
start = s.find(start_marker)
end = s.find(end_marker, start + 1)
if start < 0 or end < 0:
    raise SystemExit('SportsScheduleScreen function boundaries not found; refusing unsafe rewrite')

screen = '''@Composable
fun SportsScheduleScreen(initialLeague: String? = null, onBack: () -> Unit, onEvent: (SportsEvent) -> Unit) {
    val scope = rememberCoroutineScope()
    var events by remember { mutableStateOf<List<SportsEvent>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var filter by remember { mutableStateOf("ALL") }
    var leagueFilter by remember { mutableStateOf(initialLeague ?: "ALL") }

    fun refresh() {
        scope.launch {
            loading = true
            error = null
            runCatching { SportsScheduleService.load() }
                .onSuccess { events = it }
                .onFailure { error = it.message ?: "Unable to load schedules" }
            loading = false
        }
    }

    LaunchedEffect(initialLeague) { leagueFilter = initialLeague ?: "ALL" }
    LaunchedEffect(Unit) { refresh() }

    val statusVisible = when (filter) {
        "LIVE" -> events.filter { it.isLive }
        "UPCOMING" -> events.filter { it.isUpcoming }
        else -> events
    }
    val visible = if (leagueFilter == "ALL") statusVisible else statusVisible.filter { it.league.equals(leagueFilter, true) }
    val leagueChoices = listOf(
        "ALL", "NFL", "NBA", "WNBA", "NCAA FB", "NCAA FCS", "NCAA BB", "NCAA WBB",
        "MLB", "NCAA BASEBALL", "NHL", "NCAA MEN HOCKEY", "NCAA WOMEN HOCKEY", "NCAA SOFTBALL",
        "NCAA VB", "NCAA MEN SOCCER", "NCAA WOMEN SOCCER", "NCAA MEN LAX", "NCAA WOMEN LAX", "NCAA WRESTLING",
        "MLS", "EPL", "LaLiga", "Bundesliga", "Serie A", "Ligue 1", "UCL", "UEL", "NWSL",
        "UFC", "BOXING", "RUGBY", "RUGBY LEAGUE", "LACROSSE", "NLL", "VOLLEYBALL", "VOLLEYBALL MEN",
        "GOLF PGA", "GOLF LPGA", "GOLF LIV", "TENNIS ATP", "TENNIS WTA", "AFL",
        "F1", "NASCAR", "NASCAR XFINITY", "NASCAR TRUCK", "INDYCAR", "MOTOGP",
        "WRESTLING", "WRC", "WEC", "IMSA", "FORMULA E", "MXGP", "MONSTER JAM"
    )

    Column(Modifier.fillMaxSize().background(Color(0xFF07080C))) {
        Row(Modifier.fillMaxWidth().padding(28.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("‹", color = Color.White, fontSize = 38.sp, modifier = Modifier.clickable { onBack() })
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text(if (leagueFilter == "ALL") "LIVE + UPCOMING" else leagueFilter, color = Color.White, fontSize = 28.sp, fontWeight = FontWeight.Black)
                Text(if (leagueFilter == "ALL") "Sports schedule" else "$leagueFilter schedule", color = Color(0xFF858B98), fontSize = 12.sp)
            }
            TextButton(onClick = { refresh() }) { Text("REFRESH") }
        }
        Row(Modifier.padding(horizontal = 28.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("ALL", "LIVE", "UPCOMING").forEach { value ->
                FilterChip(selected = filter == value, onClick = { filter = value }, label = { Text(value) })
            }
        }
        LazyRow(
            modifier = Modifier.fillMaxWidth(),
            contentPadding = PaddingValues(horizontal = 28.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(leagueChoices) { league ->
                FilterChip(
                    selected = leagueFilter.equals(league, true),
                    onClick = { leagueFilter = league },
                    label = { Text(league) }
                )
            }
        }
        when {
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = Color(0xFFFF1744))
            }
            error != null -> Box(Modifier.fillMaxSize().padding(30.dp), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("SCHEDULE ERROR", color = Color(0xFFFF536C), fontWeight = FontWeight.Black)
                    Spacer(Modifier.height(8.dp))
                    Text(error!!, color = Color.White)
                    Spacer(Modifier.height(12.dp))
                    TextButton(onClick = { refresh() }) { Text("TRY AGAIN") }
                }
            }
            visible.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(
                    if (filter == "LIVE") "Nothing live right now"
                    else if (leagueFilter == "ALL") "No events found"
                    else "No $leagueFilter events found",
                    color = Color(0xFF858B98)
                )
            }
            else -> LazyColumn(
                contentPadding = PaddingValues(28.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                items(visible, key = { it.id }) { event ->
                    ScheduleEventCard(event) { onEvent(event) }
                }
            }
        }
    }
}

'''
s = s[:start] + screen + s[end:]
SCREEN.write_text(s, encoding='utf-8')

# This UI rewrite runs immediately before the official NCAA patch in the
# production workflow. Re-apply the NCAA source patch here so this rewrite
# cannot erase the authoritative college-schedule integration.
subprocess.run(['python3', 'scripts/patch_official_ncaa_schedule_sources.py'], check=True)

print('Schedule UI build repair applied and official NCAA schedule patch reapplied after the UI rewrite.')
