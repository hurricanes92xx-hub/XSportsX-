#!/usr/bin/env python3
from pathlib import Path

SERVICE = Path('app/src/main/java/com/xsportsx/app/SportsScheduleService.kt')

s = SERVICE.read_text(encoding='utf-8')

if 'private const val SPECIAL_FEED_URL' not in s:
    anchor = '    private const val CONNECT_TIMEOUT_MS = 1_800\n'
    inject = '''    private const val SPECIAL_FEED_URL = "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/android-app/data/schedule_feed.json"
    private val SPECIAL_FEED_LEAGUES = setOf("WRESTLING", "WWE", "AEW", "TNA", "WRC", "WEC", "IMSA", "FORMULA E", "MXGP", "MONSTER JAM")
'''
    if anchor not in s:
        raise SystemExit('schedule constants anchor not found')
    s = s.replace(anchor, anchor + inject, 1)

if 'fetchSpecialScheduleFeed()' not in s:
    anchor = '        results.flatten()\n'
    replacement = '''        (results.flatten() + fetchSpecialScheduleFeed())
'''
    if anchor not in s:
        raise SystemExit('schedule result anchor not found')
    s = s.replace(anchor, replacement, 1)

# Allow special-feed events through the final canonical-league gate.
s = s.replace(
    'knownLeague && (event.isLive || event.isPregame() || event.isUpcoming)',
    '(knownLeague || SPECIAL_FEED_LEAGUES.contains(league)) && (event.isLive || event.isPregame() || event.isUpcoming)',
    1,
)

if 'private fun fetchSpecialScheduleFeed()' not in s:
    anchor = '    private fun buildWindows(today: LocalDate): List<ScheduleWindow> {\n'
    inject = '''    private fun fetchSpecialScheduleFeed(): List<SportsEvent> = runCatching {
        val root = JSONObject(http(SPECIAL_FEED_URL))
        val events = root.optJSONArray("events") ?: return@runCatching emptyList()
        buildList {
            for (i in 0 until events.length()) {
                val e = events.optJSONObject(i) ?: continue
                val league = normalizeLeague(e.optString("league"))
                if (!SPECIAL_FEED_LEAGUES.contains(league)) continue
                val title = e.optString("title").trim()
                val start = e.optString("start").trim()
                if (title.isBlank() || start.isBlank()) continue
                add(SportsEvent(
                    "special-${league}-${i}-${start}",
                    when (league) {
                        "WRC", "WEC", "IMSA", "FORMULA E", "MXGP", "MONSTER JAM" -> "Racing"
                        "WRESTLING", "WWE", "AEW", "TNA" -> "Wrestling"
                        else -> league
                    },
                    league,
                    title,
                    start,
                    e.optString("tag").ifBlank { "EVENT" },
                    "pre",
                    title,
                    league,
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    ""
                ))
            }
        }
    }.getOrDefault(emptyList())

'''
    if anchor not in s:
        raise SystemExit('schedule window anchor not found')
    s = s.replace(anchor, inject + anchor, 1)

SERVICE.write_text(s, encoding='utf-8')
print('Special schedule feed merged into the shared schedule service')
