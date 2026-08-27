#!/usr/bin/env python3
from pathlib import Path

SERVICE = Path('app/src/main/java/com/xsportsx/app/SportsScheduleService.kt')
SCREEN = Path('app/src/main/java/com/xsportsx/app/SportsScheduleScreen.kt')

s = SERVICE.read_text(encoding='utf-8')

if 'private const val SPECIAL_FEED_URL' not in s:
    anchor = '    private const val CONNECT_TIMEOUT_MS = 1_800\n'
    inject = '''    private const val SPECIAL_FEED_URL = "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/android-app/data/schedule_feed.json"\n    private val SPECIAL_FEED_LEAGUES = setOf("WRESTLING", "WWE", "AEW", "TNA", "WRC", "WEC", "IMSA", "FORMULA E", "MXGP", "MONSTER JAM", "MOTOGP", "F1")\n'''
    if anchor not in s:
        raise SystemExit('schedule constants anchor not found')
    s = s.replace(anchor, anchor + inject, 1)

s = s.replace('            setRequestProperty("Accept-Encoding", "gzip")\n', '', 1)

if 'fetchSpecialScheduleFeed()' not in s:
    anchor = '        results.flatten()\n'
    replacement = '        (results.flatten() + fetchSpecialScheduleFeed())\n'
    if anchor not in s:
        raise SystemExit('schedule result anchor not found')
    s = s.replace(anchor, replacement, 1)

s = s.replace(
    'knownLeague && (event.isLive || event.isPregame() || event.isUpcoming)',
    '(knownLeague || SPECIAL_FEED_LEAGUES.contains(league)) && (event.isLive || event.isPregame() || event.isUpcoming)',
    1,
)

# Add backed NCAA sports feeds. groups=50 asks ESPN for the full Division I slate.
anchor = '        ScheduleLeague("BOXING", "Boxing", "boxing/boxing", "https://www.boxing.com/")\n'
college = '''        ScheduleLeague("NCAA VB", "Volleyball", "volleyball/womens-college-volleyball", "https://www.ncaa.com/sports/volleyball-women", "groups=50"),\n        ScheduleLeague("NCAA MVB", "Volleyball", "volleyball/mens-college-volleyball", "https://www.ncaa.com/sports/volleyball-men", "groups=50"),\n        ScheduleLeague("NCAA BASEBALL", "Baseball", "baseball/college-baseball", "https://www.ncaa.com/sports/baseball", "groups=50"),\n        ScheduleLeague("NCAA SOFTBALL", "Softball", "softball/college-softball", "https://www.ncaa.com/sports/softball", "groups=50"),\n        ScheduleLeague("NCAA MEN HOCKEY", "Hockey", "hockey/mens-college-hockey", "https://www.ncaa.com/sports/icehockey-men", "groups=50"),\n        ScheduleLeague("NCAA WOMEN HOCKEY", "Hockey", "hockey/womens-college-hockey", "https://www.ncaa.com/sports/icehockey-women", "groups=50"),\n        ScheduleLeague("NCAA MEN SOCCER", "Soccer", "soccer/usa.ncaa.m.1", "https://www.ncaa.com/sports/soccer-men", "groups=50"),\n        ScheduleLeague("NCAA WOMEN SOCCER", "Soccer", "soccer/usa.ncaa.w.1", "https://www.ncaa.com/sports/soccer-women", "groups=50"),\n        ScheduleLeague("NCAA MEN LAX", "Lacrosse", "lacrosse/mens-college-lacrosse", "https://www.ncaa.com/sports/lacrosse-men", "groups=50"),\n        ScheduleLeague("NCAA WOMEN LAX", "Lacrosse", "lacrosse/womens-college-lacrosse", "https://www.ncaa.com/sports/lacrosse-women", "groups=50"),\n'''
if 'ScheduleLeague("NCAA VB", "Volleyball"' not in s and anchor in s:
    s = s.replace(anchor, anchor + college, 1)

# Keep every newly backed category selectable in the schedule UI.
ui_anchor = '        "NCAA VB", "NCAA MEN SOCCER",'
ui_add = '        "NCAA VB", "NCAA MVB", "NCAA BASEBALL", "NCAA SOFTBALL", "NCAA MEN HOCKEY", "NCAA WOMEN HOCKEY", "NCAA MEN SOCCER", "NCAA WOMEN SOCCER", "NCAA MEN LAX", "NCAA WOMEN LAX",'
if '"NCAA MVB"' not in s and ui_anchor in s:
    s = s.replace(ui_anchor, ui_add, 1)

# Combat endpoints can return event cards without team-style competitors. Keep those events.
old = '''            val competition = event.optJSONArray("competitions")?.optJSONObject(0) ?: continue\n            val competitors = competition.optJSONArray("competitors") ?: continue\n\n            var home = ""\n'''
new = '''            val competition = event.optJSONArray("competitions")?.optJSONObject(0) ?: JSONObject()\n            val competitors = competition.optJSONArray("competitors")\n\n            var home = ""\n'''
if old in s:
    s = s.replace(old, new, 1)

old = '''            for (j in 0 until competitors.length()) {\n                val competitor = competitors.optJSONObject(j) ?: continue\n'''
new = '''            if (competitors != null) for (j in 0 until competitors.length()) {\n                val competitor = competitors.optJSONObject(j) ?: continue\n'''
if old in s:
    s = s.replace(old, new, 1)

old = '''            val start = event.optString("date")\n                .ifBlank { competition.optString("startDate") }\n            if (start.isBlank() || home.isBlank() || away.isBlank()) continue\n\n            val rawName = event.optString("name")\n'''
new = '''            val start = event.optString("date")\n                .ifBlank { competition.optString("startDate") }\n            if (start.isBlank()) continue\n\n            val rawName = event.optString("name")\n'''
if old in s:
    s = s.replace(old, new, 1)

old = '''            val title = rawName.ifBlank { "$away vs $home" }\n\n            val youtube = event.optString("youtubeVideoId")\n'''
new = '''            val title = rawName.ifBlank {\n                if (home.isNotBlank() && away.isNotBlank()) "$away vs $home" else league.league\n            }\n\n            val combatEvent = league.league.equals("UFC", true) || league.league.equals("BOXING", true)\n            if (!combatEvent && (home.isBlank() || away.isBlank())) continue\n\n            val youtube = event.optString("youtubeVideoId")\n'''
if old in s:
    s = s.replace(old, new, 1)

if 'private fun fetchSpecialScheduleFeed()' not in s:
    anchor = '    private fun buildWindows(today: LocalDate): List<ScheduleWindow> {\n'
    inject = '''    private fun specialEventDurationMinutes(league: String, event: JSONObject): Long =\n        event.optLong("durationMinutes", when (league) {\n            "WRESTLING" -> 210L\n            "WRC", "WEC", "IMSA", "FORMULA E", "MXGP", "MOTOGP", "F1" -> 240L\n            "MONSTER JAM" -> 180L\n            else -> 180L\n        }).coerceIn(30L, 720L)\n\n    private fun specialEventState(start: String, league: String, event: JSONObject): String {\n        val startMillis = runCatching { java.time.Instant.parse(start).toEpochMilli() }.getOrDefault(0L)\n        if (startMillis <= 0L) return "pre"\n        val now = System.currentTimeMillis()\n        val endMillis = startMillis + specialEventDurationMinutes(league, event) * 60_000L\n        return when {\n            now < startMillis -> "pre"\n            now < endMillis -> "in"\n            else -> "post"\n        }\n    }\n\n    private fun fetchSpecialScheduleFeed(): List<SportsEvent> = runCatching {\n        val root = JSONObject(http(SPECIAL_FEED_URL))\n        val events = root.optJSONArray("events") ?: return@runCatching emptyList()\n        buildList {\n            for (i in 0 until events.length()) {\n                val e = events.optJSONObject(i) ?: continue\n                val rawLeague = e.optString("league").trim().uppercase()\n                val league = when (rawLeague) {\n                    "WWE", "AEW", "TNA" -> "WRESTLING"\n                    else -> normalizeLeague(rawLeague)\n                }\n                if (!SPECIAL_FEED_LEAGUES.contains(league)) continue\n                val title = e.optString("title").trim()\n                val start = e.optString("start").trim()\n                if (title.isBlank() || start.isBlank()) continue\n                add(SportsEvent(\n                    "special-${league}-${i}-${start}",\n                    when (league) {\n                        "WRC", "WEC", "IMSA", "FORMULA E", "MXGP", "MONSTER JAM", "MOTOGP", "F1" -> "Racing"\n                        "WRESTLING" -> "Wrestling"\n                        else -> league\n                    },\n                    league,\n                    title,\n                    start,\n                    e.optString("tag").ifBlank { "EVENT" },\n                    specialEventState(start, league, e),\n                    title,\n                    league,\n                    "",\n                    "",\n                    "",\n                    "",\n                    "",\n                    ""\n                ))\n            }\n        }\n    }.getOrDefault(emptyList())\n\n'''
    if anchor not in s:
        raise SystemExit('schedule window anchor not found')
    s = s.replace(anchor, inject + anchor, 1)

SERVICE.write_text(s, encoding='utf-8')

if SCREEN.exists():
    t = SCREEN.read_text(encoding='utf-8')
    t = t.replace('SportsScheduleService.load(leagueFilter)', 'SportsScheduleService.load()')
    old_choices = 'val leagueChoices = listOf("ALL", "NFL", "NCAA FB", "NBA", "NCAA BB", "MLB", "NHL", "UFC", "BOXING")'
    new_choices = 'val leagueChoices = SportsScheduleService.uiLeagueChoices.let { listOf("ALL") + it.filter { choice -> choice != "ALL" }.distinct() }'
    if old_choices in t:
        t = t.replace(old_choices, new_choices, 1)
    old_label = '''                    Text(when { event.league.equals("UFC", true) -> "UFC • FIGHT EVENT"; event.league.equals("BOXING", true) -> "BOXING • EVENT NIGHT"; else -> "F1 • GRAND PRIX" }, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black, letterSpacing = 1.4.sp)'''
    new_label = '''                    Text(specialCardKicker(event), color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black, letterSpacing = 1.4.sp)'''
    if old_label in t:
        t = t.replace(old_label, new_label, 1)
    old_text = 'Text(if (isUfc) "UFC" else "BOXING", color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Black, letterSpacing = 1.4.sp)'
    new_text = 'Text(event.league.uppercase(), color = Color.White, fontSize = if (event.league.length > 8) 9.sp else 13.sp, fontWeight = FontWeight.Black, letterSpacing = 1.0.sp)'
    if old_text in t:
        t = t.replace(old_text, new_text, 1)
    if 'private fun specialCardKicker(event: SportsEvent)' not in t:
        marker = '@Composable\nprivate fun EventArtBadge'
        helper = '''private fun specialCardKicker(event: SportsEvent): String = when (event.league.uppercase()) {\n    "UFC" -> "UFC • FIGHT EVENT"\n    "BOXING" -> "BOXING • EVENT NIGHT"\n    "FORMULA E" -> "FORMULA E • ePRIX"\n    "MXGP" -> "MXGP • GRAND PRIX"\n    "MONSTER JAM" -> "MONSTER JAM • EVENT"\n    "MOTOGP" -> "MOTOGP • GRAND PRIX"\n    "WRC" -> "WRC • RALLY"\n    "WEC" -> "WEC • ENDURANCE"\n    "IMSA" -> "IMSA • SPORTS CAR"\n    "F1" -> "F1 • GRAND PRIX"\n    "WRESTLING" -> "WRESTLING • EVENT"\n    else -> "${event.league.uppercase()} • EVENT"\n}\n\n'''
        if marker in t:
            t = t.replace(marker, helper + marker, 1)
    SCREEN.write_text(t, encoding='utf-8')

print('Schedule patch updated: combat events without team competitors, NCAA volleyball/college feeds, and correct special-event card labels.')
