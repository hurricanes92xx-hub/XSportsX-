#!/usr/bin/env python3
from pathlib import Path

SERVICE = Path('app/src/main/java/com/xsportsx/app/SportsScheduleService.kt')
SCREEN = Path('app/src/main/java/com/xsportsx/app/SportsScheduleScreen.kt')

s = SERVICE.read_text(encoding='utf-8')

# Keep the yearly horizon, but do not let one slow/unsupported league cancel the
# entire schedule load. More importantly, when a league is selected, only query
# that league instead of waiting on every league in the catalog.
old_window = 'val today=LocalDate.now(ZoneId.systemDefault());val end=today.plusDays(30);val dates="${today.format(DateTimeFormatter.BASIC_ISO_DATE)}-${end.format(DateTimeFormatter.BASIC_ISO_DATE)}";val limiter=Semaphore(8)'
new_window = 'val today=LocalDate.now(ZoneId.systemDefault());val end=today.plusDays(370);val dates="${today.format(DateTimeFormatter.BASIC_ISO_DATE)}-${end.format(DateTimeFormatter.BASIC_ISO_DATE)}";val limiter=Semaphore(6)'
if old_window in s:
    s = s.replace(old_window, new_window, 1)
elif 'today.plusDays(370)' in s:
    s = s.replace('val limiter=Semaphore(8)', 'val limiter=Semaphore(6)', 1)
else:
    raise SystemExit('schedule window pattern not found')

old_load = '''suspend fun load():List<SportsEvent> = withContext(Dispatchers.IO) {
        // Keep the interactive request small. Yearly/season-wide discovery is handled by the
        // scheduled refresh pipeline; the UI only needs a rolling near-term window.
        val today=LocalDate.now(ZoneId.systemDefault());val end=today.plusDays(370);val dates="${today.format(DateTimeFormatter.BASIC_ISO_DATE)}-${end.format(DateTimeFormatter.BASIC_ISO_DATE)}";val limiter=Semaphore(6)
        val results=withTimeout(28_000L){coroutineScope{leagues.map{league->async{limiter.withPermit{fetchLeagueWithFallbacks(league,dates)}}}.awaitAll()}}
        results.flatten().distinctBy{it.id.ifBlank{it.title+it.startUtc+it.league}}.filter{it.isLive||it.isUpcoming}.sortedWith(compareBy<SportsEvent>{!it.isLive}.thenBy{it.startUtc})
    }'''
new_load = '''suspend fun load(leagueFilter:String? = null):List<SportsEvent> = withContext(Dispatchers.IO) {
        val today=LocalDate.now(ZoneId.systemDefault())
        val end=today.plusDays(370)
        val dates="${today.format(DateTimeFormatter.BASIC_ISO_DATE)}-${end.format(DateTimeFormatter.BASIC_ISO_DATE)}"
        val selected=leagueFilter?.trim().orEmpty()
        val canonical=if(selected.isBlank() || selected.equals("ALL",true)) "" else canonicalLeagueFor(selected)
        val targetLeagues=if(canonical.isBlank()) leagues else leagues.filter{it.league.equals(canonical,true)}
        if(targetLeagues.isEmpty()) return@withContext emptyList()
        val results=coroutineScope {
            targetLeagues.map { league ->
                async {
                    runCatching { withTimeout(7_000L) { limiter.withPermit { fetchLeagueWithFallbacks(league,dates) } } }
                        .getOrDefault(emptyList())
                }
            }.awaitAll()
        }
        results.flatten()
            .distinctBy{it.id.ifBlank{it.title+it.startUtc+it.league}}
            .filter{it.isLive||it.isUpcoming}
            .sortedWith(compareBy<SportsEvent>{!it.isLive}.thenBy{it.startUtc})
    }'''
if old_load in s:
    s = s.replace(old_load, new_load, 1)
elif 'suspend fun load(leagueFilter:String? = null)' not in s:
    raise SystemExit('schedule load block not found')

# Fix canonical labels that were being uppercased even though the service catalog
# uses mixed-case names such as LaLiga. This keeps exact league isolation intact.
old_canon = '''        "FORMULA 1","FORMULA1" -> "F1"
        "MOTO GP","MOTOGP" -> "MOTOGP"
        "FORMULA E","FORMULAE" -> "FORMULA E"
        "MONSTER JAM","MONSTERJAM" -> "MONSTER JAM"
        else -> label.trim().uppercase()'''
new_canon = '''        "FORMULA 1","FORMULA1" -> "F1"
        "MOTO GP","MOTOGP" -> "MOTOGP"
        "FORMULA E","FORMULAE" -> "FORMULA E"
        "MONSTER JAM","MONSTERJAM" -> "MONSTER JAM"
        "LALIGA" -> "LaLiga"
        "SERIE A" -> "Serie A"
        "BUNDESLIGA" -> "Bundesliga"
        "LIGUE 1" -> "Ligue 1"
        "NCAA BASEBALL" -> "NCAA BASEBALL"
        "NCAA VB","NCAA VOLLEYBALL" -> "NCAA VB"
        else -> label.trim().uppercase()'''
if old_canon in s:
    s = s.replace(old_canon, new_canon, 1)

SERVICE.write_text(s, encoding='utf-8')

# The schedule screen must pass its selected league into the service; otherwise
# it loads every league and filters after the expensive network operation.
t = SCREEN.read_text(encoding='utf-8')
old_call = 'runCatching { SportsScheduleService.load() }'
new_call = 'runCatching { SportsScheduleService.load(leagueFilter) }'
if old_call in t:
    t = t.replace(old_call, new_call, 1)
elif new_call not in t:
    raise SystemExit('schedule screen load call not found')
SCREEN.write_text(t, encoding='utf-8')

print('league schedules now load independently with exact filtering and per-league timeouts')
