#!/usr/bin/env python3
from pathlib import Path

SERVICE = Path('app/src/main/java/com/xsportsx/app/SportsScheduleService.kt')
s = SERVICE.read_text(encoding='utf-8')

# Idempotent production patch: ESPN remains the broad future schedule source;
# NCAA's first-party scoreboard is authoritative for same-day college events.
if 'NCAA_OFFICIAL_SCOREBOARD_V2' in s:
    print('NCAA official scoreboard fallback already present')
    raise SystemExit(0)

model = '''private data class OfficialNCAAFeed(
    val league: String,
    val sport: String,
    val sportCode: String,
    val division: Int,
    val officialUrl: String
)

'''
anchor = 'private data class ScheduleWindow(val start: LocalDate, val end: LocalDate) {'
if 'private data class OfficialNCAAFeed' not in s:
    if anchor not in s:
        print('NCAA patch skipped: schedule window model anchor moved')
        raise SystemExit(0)
    s = s.replace(anchor, model + anchor, 1)

anchor = '    private const val CONNECT_TIMEOUT_MS = 1_800\n'
constants = '''    // NCAA_OFFICIAL_SCOREBOARD_V2
    private const val NCAA_GRAPHQL_URL = "https://sdataprod.ncaa.com/"
    private const val NCAA_SCOREBOARD_HASH = "7287cda610a9326931931080cb3a604828febe6fe3c9016a7e4a36db99efdb7c"
'''
if 'NCAA_SCOREBOARD_HASH' not in s:
    if anchor not in s:
        print('NCAA patch skipped: timeout constants anchor moved')
        raise SystemExit(0)
    s = s.replace(anchor, anchor + constants, 1)

feeds = '''    private val officialNCAAFeeds = listOf(
        OfficialNCAAFeed("NCAA FB", "Football", "MFB", 11, "https://www.ncaa.com/sports/football/fbs"),
        OfficialNCAAFeed("NCAA FCS", "Football", "MFB", 12, "https://www.ncaa.com/sports/football/fcs"),
        OfficialNCAAFeed("NCAA BB", "Basketball", "MBB", 1, "https://www.ncaa.com/sports/basketball-men/d1"),
        OfficialNCAAFeed("NCAA WBB", "Basketball", "WBB", 1, "https://www.ncaa.com/sports/basketball-women/d1"),
        OfficialNCAAFeed("NCAA BASEBALL", "Baseball", "MBA", 1, "https://www.ncaa.com/sports/baseball/d1"),
        OfficialNCAAFeed("NCAA SOFTBALL", "Softball", "WSB", 1, "https://www.ncaa.com/sports/softball/d1"),
        OfficialNCAAFeed("NCAA MEN HOCKEY", "Hockey", "MIH", 1, "https://www.ncaa.com/sports/icehockey-men/d1"),
        OfficialNCAAFeed("NCAA WOMEN HOCKEY", "Hockey", "WIH", 1, "https://www.ncaa.com/sports/icehockey-women/d1"),
        OfficialNCAAFeed("NCAA VB", "Volleyball", "WVB", 1, "https://www.ncaa.com/sports/volleyball-women/d1"),
        OfficialNCAAFeed("NCAA MVB", "Volleyball", "MVB", 1, "https://www.ncaa.com/sports/volleyball-men/d1"),
        OfficialNCAAFeed("NCAA MEN SOCCER", "Soccer", "MSO", 1, "https://www.ncaa.com/sports/soccer-men/d1"),
        OfficialNCAAFeed("NCAA WOMEN SOCCER", "Soccer", "WSO", 1, "https://www.ncaa.com/sports/soccer-women/d1"),
        OfficialNCAAFeed("NCAA MEN LAX", "Lacrosse", "MLA", 1, "https://www.ncaa.com/sports/lacrosse-men/d1"),
        OfficialNCAAFeed("NCAA WOMEN LAX", "Lacrosse", "WLA", 1, "https://www.ncaa.com/sports/lacrosse-women/d1"),
        OfficialNCAAFeed("NCAA FIELD HOCKEY", "Field Hockey", "WFH", 1, "https://www.ncaa.com/sports/fieldhockey/d1"),
        OfficialNCAAFeed("NCAA BEACH VOLLEYBALL", "Beach Volleyball", "WSV", 1, "https://www.ncaa.com/sports/beach-volleyball/d1"),
        OfficialNCAAFeed("NCAA WATER POLO", "Water Polo", "MWP", 1, "https://www.ncaa.com/sports/waterpolo-men/d1"),
        OfficialNCAAFeed("NCAA WOMEN WATER POLO", "Water Polo", "WWP", 1, "https://www.ncaa.com/sports/waterpolo-women/d1")
    )

'''
if 'private val officialNCAAFeeds' not in s:
    anchor = '    private val leagues = listOf(\n'
    if anchor not in s:
        print('NCAA patch skipped: league catalog anchor moved')
        raise SystemExit(0)
    s = s.replace(anchor, feeds + anchor, 1)

official_today = '''        val officialToday = coroutineScope {
            val officialLimiter = Semaphore(6)
            officialNCAAFeeds.map { feed ->
                async {
                    officialLimiter.withPermit {
                        withTimeoutOrNull(HTTP_TIMEOUT_MS) {
                            runCatching { fetchOfficialNCAAFeed(feed, today) }.getOrDefault(emptyList())
                        }.orEmpty()
                    }
                }
            }.awaitAll().flatten()
        }

'''
old = '''        results.flatten()
            .filter { event ->
                val league = normalizeLeague(event.league)
                val knownLeague = leagues.any { it.league == league }
                knownLeague && (event.isLive || event.isPregame() || event.isUpcoming)
            }'''
new = official_today + '''        (results.flatten() + officialToday)
            .filter { event ->
                val league = normalizeLeague(event.league)
                val knownLeague = leagues.any { it.league == league } || officialNCAAFeeds.any { it.league == league }
                knownLeague && (event.isLive || event.isPregame() || event.isUpcoming)
            }'''
if old in s:
    s = s.replace(old, new, 1)
else:
    # Earlier production patches may already have changed the result pipeline.
    # Never block the APK build merely because that stable text anchor moved.
    # The existing ESPN schedule pipeline remains the fallback source.
    SERVICE.write_text(s, encoding='utf-8')
    print('NCAA official scoreboard patch skipped: result pipeline already changed; keeping existing schedule sources')
    raise SystemExit(0)

old = '''            .distinctBy { event ->
                event.id.ifBlank {
                    listOf(event.league, normalize(event.home), normalize(event.away), event.startUtc).joinToString("|")
                }
            }'''
if old in s:
    s = s.replace(old, '            .distinctBy { event -> canonicalKey(event) }', 1)

implementation = r'''    private fun fetchOfficialNCAAFeed(feed: OfficialNCAAFeed, date: LocalDate): List<SportsEvent> {
        // NCAA's persisted scoreboard query supplies authoritative same-day
        // college results while ESPN remains the broad future schedule source.
        val contestDate = date.format(DateTimeFormatter.ofPattern("yyyy/MM/dd"))
        val seasonYear = if (date.monthValue < 8) date.year - 1 else date.year
        val variables = JSONObject()
            .put("sportCode", feed.sportCode)
            .put("division", feed.division)
            .put("seasonYear", seasonYear)
            .put("contestDate", contestDate)
        val extensions = JSONObject().put("persistedQuery", JSONObject()
            .put("version", 1)
            .put("sha256Hash", NCAA_SCOREBOARD_HASH))
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
                val seo = team.optString("seoname")
                val logo = if (seo.isBlank()) "" else
                    "https://www.ncaa.com/sites/default/files/images/logos/schools/bgl/$seo.svg"
                val score = team.opt("score")?.toString().orEmpty()
                if (team.optBoolean("isHome", false)) {
                    home = name; homeLogo = logo; homeScore = score
                } else {
                    away = name; awayLogo = logo; awayScore = score
                }
            }
            if (home.isBlank() || away.isBlank()) continue
            val state = when (contest.optString("gameState").uppercase()) {
                "I" -> "in"
                "F" -> "post"
                else -> "pre"
            }
            val detail = contest.optString("finalMessage")
                .ifBlank { contest.optString("currentPeriod") }
                .ifBlank { if (homeScore.isNotBlank() || awayScore.isNotBlank()) "$awayScore - $homeScore" else "" }
            val epoch = contest.optString("startTimeEpoch").toLongOrNull()
            if (epoch == null || epoch <= 0L) continue
            val start = java.time.Instant.ofEpochMilli(epoch).toString()
            val contestId = contest.optString("contestId").ifBlank { "$contestDate-$i" }
            out += SportsEvent(
                "ncaa-${feed.league}-$contestId", feed.sport, feed.league,
                "$away vs $home", start, detail, state, home, away,
                homeLogo, awayLogo, contest.optString("broadcasterName"), "",
                feed.officialUrl, ""
            )
        }
        return out
    }

'''
if 'private fun fetchOfficialNCAAFeed' not in s:
    anchor = '    private suspend fun loadLeague(\n'
    if anchor not in s:
        SERVICE.write_text(s, encoding='utf-8')
        print('NCAA official scoreboard patch skipped: loadLeague anchor moved')
        raise SystemExit(0)
    s = s.replace(anchor, implementation + anchor, 1)

SERVICE.write_text(s, encoding='utf-8')
print('Installed resilient NCAA first-party same-day scoreboard fallback across supported college sports.')