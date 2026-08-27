#!/usr/bin/env python3
from pathlib import Path

SERVICE = Path('app/src/main/java/com/xsportsx/app/SportsScheduleService.kt')
s = SERVICE.read_text(encoding='utf-8')

# NCAA's current scoreboard backend is a first-party data source. Keep ESPN as
# the broad schedule source, then use NCAA's own scoreboard data for today's
# college slate so missing/incorrect college cards can be filled authoritatively.
if 'NCAA_GRAPHQL_HASH' not in s:
    s = s.replace(
        '    private const val CONNECT_TIMEOUT_MS = 1_800\n',
        '''    private const val CONNECT_TIMEOUT_MS = 1_800\n    private const val NCAA_GRAPHQL_URL = "https://sdataprod.ncaa.com/"\n    private const val NCAA_GRAPHQL_HASH = "7287cda610a9326931931080cb3a604828febe6fe3c9016a7e4a36db99efdb7c"\n''',
        1,
    )

if 'private data class OfficialNCAAFeed' not in s:
    anchor = 'private data class ScheduleWindow(val start: LocalDate, val end: LocalDate) {\n'
    inject = '''private data class OfficialNCAAFeed(\n    val league: String,\n    val sport: String,\n    val sportCode: String,\n    val division: Int,\n    val officialUrl: String\n)\n\n'''
    if anchor not in s:
        raise SystemExit('schedule window anchor not found')
    s = s.replace(anchor, inject + anchor, 1)

if 'OFFICIAL_NCAA_FEEDS' not in s:
    anchor = '    private val leagues = listOf(\n'
    feeds = '''    private val OFFICIAL_NCAA_FEEDS = listOf(\n        OfficialNCAAFeed("NCAA BB", "Basketball", "MBB", 1, "https://www.ncaa.com/sports/basketball-men/d1"),\n        OfficialNCAAFeed("NCAA WBB", "Basketball", "WBB", 1, "https://www.ncaa.com/sports/basketball-women/d1"),\n        OfficialNCAAFeed("NCAA BASEBALL", "Baseball", "MBA", 1, "https://www.ncaa.com/sports/baseball/d1"),\n        OfficialNCAAFeed("NCAA SOFTBALL", "Softball", "WSB", 1, "https://www.ncaa.com/sports/softball/d1"),\n        OfficialNCAAFeed("NCAA MEN HOCKEY", "Hockey", "MIH", 1, "https://www.ncaa.com/sports/icehockey-men/d1"),\n        OfficialNCAAFeed("NCAA WOMEN HOCKEY", "Hockey", "WIH", 1, "https://www.ncaa.com/sports/icehockey-women/d1"),\n        OfficialNCAAFeed("NCAA VB", "Volleyball", "WVB", 1, "https://www.ncaa.com/sports/volleyball-women/d1"),\n        OfficialNCAAFeed("NCAA MVB", "Volleyball", "MVB", 1, "https://www.ncaa.com/sports/volleyball-men/d1"),\n        OfficialNCAAFeed("NCAA MEN SOCCER", "Soccer", "MSO", 1, "https://www.ncaa.com/sports/soccer-men/d1"),\n        OfficialNCAAFeed("NCAA WOMEN SOCCER", "Soccer", "WSO", 1, "https://www.ncaa.com/sports/soccer-women/d1"),\n        OfficialNCAAFeed("NCAA MEN LAX", "Lacrosse", "MLA", 1, "https://www.ncaa.com/sports/lacrosse-men/d1"),\n        OfficialNCAAFeed("NCAA WOMEN LAX", "Lacrosse", "WLA", 1, "https://www.ncaa.com/sports/lacrosse-women/d1")\n    )\n\n'''
    if anchor not in s:
        raise SystemExit('leagues catalog anchor not found')
    s = s.replace(anchor, feeds + anchor, 1)

if 'OFFICIAL_NCAA_FEEDS.any' not in s:
    old = '                val knownLeague = leagues.any { it.league == league }\n                knownLeague && (event.isLive || event.isPregame() || event.isUpcoming)'
    new = '                val knownLeague = leagues.any { it.league == league } || OFFICIAL_NCAA_FEEDS.any { it.league == league }\n                knownLeague && (event.isLive || event.isPregame() || event.isUpcoming)'
    if old in s:
        s = s.replace(old, new, 1)

if 'fetchOfficialNCAAToday' not in s:
    old = '''        results.flatten()\n            .filter { event ->'''
    new = '''        val officialToday = fetchOfficialNCAAToday(limiter)\n\n        (results.flatten() + officialToday)\n            .filter { event ->'''
    if old not in s:
        raise SystemExit('schedule result merge anchor not found')
    s = s.replace(old, new, 1)

old = '''            .distinctBy { event ->\n                event.id.ifBlank {\n                    listOf(event.league, normalize(event.home), normalize(event.away), event.startUtc).joinToString("|")\n                }\n            }'''
new = '''            .distinctBy { event -> canonicalKey(event) }'''
if old in s:
    s = s.replace(old, new, 1)

if 'private suspend fun fetchOfficialNCAAToday' not in s:
    anchor = '    private suspend fun loadLeague(\n'
    inject = r'''    private suspend fun fetchOfficialNCAAToday(limiter: Semaphore): List<SportsEvent> = coroutineScope {
        OFFICIAL_NCAA_FEEDS.map { feed ->
            async {
                limiter.withPermit {
                    withTimeoutOrNull(HTTP_TIMEOUT_MS) {
                        runCatching { fetchOfficialNCAAFeed(feed) }.getOrDefault(emptyList())
                    }.orEmpty()
                }
            }
        }.awaitAll().flatten()
    }

    private fun fetchOfficialNCAAFeed(feed: OfficialNCAAFeed): List<SportsEvent> {
        val today = LocalDate.now(ZoneId.systemDefault())
        val contestDate = today.format(DateTimeFormatter.ofPattern("yyyy/MM/dd"))
        val variables = JSONObject()
            .put("sportCode", feed.sportCode)
            .put("division", feed.division)
            .put("seasonYear", if (today.monthValue < 8) today.year - 1 else today.year)
            .put("contestDate", contestDate)

        val extensions = JSONObject()
            .put("persistedQuery", JSONObject()
                .put("version", 1)
                .put("sha256Hash", NCAA_GRAPHQL_HASH))

        val target = NCAA_GRAPHQL_URL +
            "?extensions=" + java.net.URLEncoder.encode(extensions.toString(), "UTF-8") +
            "&variables=" + java.net.URLEncoder.encode(variables.toString(), "UTF-8")

        val root = JSONObject(http(target))
        val contests = root.optJSONObject("data")?.optJSONArray("contests") ?: return emptyList()
        val out = ArrayList<SportsEvent>(contests.length())

        for (i in 0 until contests.length()) {
            val contest = contests.optJSONObject(i) ?: continue
            val teams = contest.optJSONArray("teams") ?: continue
            var home = ""
            var away = ""
            var homeLogo = ""
            var awayLogo = ""
            var homeScore = ""
            var awayScore = ""

            for (j in 0 until teams.length()) {
                val team = teams.optJSONObject(j) ?: continue
                val name = team.optString("nameShort")
                    .ifBlank { team.optString("name6Char") }
                    .ifBlank { team.optString("seoname") }
                val seo = team.optString("seoname").trim()
                val logo = if (seo.isBlank()) "" else
                    "https://www.ncaa.com/sites/default/files/images/logos/schools/bgl/$seo.svg"
                val score = team.opt("score")?.toString().orEmpty()
                if (team.optBoolean("isHome", false)) {
                    home = name
                    homeLogo = logo
                    homeScore = score
                } else {
                    away = name
                    awayLogo = logo
                    awayScore = score
                }
            }

            if (home.isBlank() || away.isBlank()) continue

            val start = contest.optString("startTime")
                .ifBlank { contest.optString("startDate") }
            if (start.isBlank()) continue

            val state = when (contest.optString("gameState").uppercase()) {
                "I" -> "in"
                "F" -> "post"
                else -> "pre"
            }
            val detail = contest.optString("finalMessage")
                .ifBlank { contest.optString("currentPeriod") }
                .ifBlank {
                    if (homeScore.isNotBlank() || awayScore.isNotBlank()) "$awayScore - $homeScore" else ""
                }

            val title = "$away vs $home"
            val id = "ncaa-${feed.league}-${contest.optString("contestId").ifBlank { i.toString() }}"
            out += SportsEvent(
                id,
                feed.sport,
                feed.league,
                title,
                start,
                detail,
                state,
                home,
                away,
                homeLogo,
                awayLogo,
                contest.optString("broadcasterName"),
                "",
                feed.officialUrl,
                ""
            )
        }
        return out
    }

'''
    if anchor not in s:
        raise SystemExit('loadLeague anchor not found')
    s = s.replace(anchor, inject + anchor, 1)

SERVICE.write_text(s, encoding='utf-8')

# fix_schedule_ui_build.py rewrites the stable screen after this patch. Run this
# script after that rewrite and make sure the NCAA men's volleyball catalog is visible.
SCREEN = Path('app/src/main/java/com/xsportsx/app/SportsScheduleScreen.kt')
if SCREEN.exists():
    t = SCREEN.read_text(encoding='utf-8')
    if '"NCAA MVB"' not in t:
        t = t.replace('"NCAA VB", "NCAA MEN SOCCER"', '"NCAA VB", "NCAA MVB", "NCAA MEN SOCCER"', 1)
    SCREEN.write_text(t, encoding='utf-8')

print('Added first-party NCAA GraphQL scoreboard fallback for today across DI college sports; ESPN remains the future-schedule source.')
