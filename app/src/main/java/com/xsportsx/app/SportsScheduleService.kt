package com.xsportsx.app

/**
 * Canonical schedule facade used by Mobile and TV.
 *
 * ScheduleEngine owns the runtime schedule state. This facade remains the
 * compatibility API for older screens, but it no longer creates an independent
 * provider request path. Aggregate labels such as WRESTLING are UI groups,
 * not provider identities.
 */
object SportsScheduleService {
    private val uiChoices = listOf(
        "NFL", "NBA", "WNBA", "NCAA FB", "NCAA FCS", "NCAA BB", "NCAA WBB", "MLB", "NCAA BASEBALL", "NHL",
        "NCAA MEN HOCKEY", "NCAA WOMEN HOCKEY", "NCAA SOFTBALL", "NCAA VB", "NCAA MEN SOCCER", "NCAA WOMEN SOCCER",
        "NCAA MEN LAX", "NCAA WOMEN LAX", "MLS", "EPL", "LaLiga", "Bundesliga", "Serie A", "Ligue 1", "UCL", "UEL", "NWSL",
        "UFC", "BOXING", "WRESTLING"
    )

    fun normalizeLeague(label: String): String = when (label.trim().uppercase()) {
        "COLLEGE FOOTBALL", "NCAA FOOTBALL", "NCAAF", "NCAA FBS" -> "NCAA FB"
        "COLLEGE FCS", "NCAA FOOTBALL CHAMPIONSHIP", "NCAA FCS FOOTBALL" -> "NCAA FCS"
        "COLLEGE BASKETBALL", "NCAA MEN", "NCAAM" -> "NCAA BB"
        "NCAA WOMEN", "NCAAW" -> "NCAA WBB"
        "COLLEGE BASEBALL" -> "NCAA BASEBALL"
        "COLLEGE SOFTBALL" -> "NCAA SOFTBALL"
        "COLLEGE MEN'S HOCKEY" -> "NCAA MEN HOCKEY"
        "COLLEGE WOMEN'S HOCKEY" -> "NCAA WOMEN HOCKEY"
        "COLLEGE MEN'S SOCCER", "NCAA MEN'S SOCCER" -> "NCAA MEN SOCCER"
        "COLLEGE WOMEN'S SOCCER", "NCAA WOMEN'S SOCCER" -> "NCAA WOMEN SOCCER"
        "COLLEGE WOMEN'S LACROSSE" -> "NCAA WOMEN LAX"
        "COLLEGE MEN'S LACROSSE" -> "NCAA MEN LAX"
        "NCAA VOLLEYBALL", "COLLEGE VOLLEYBALL" -> "NCAA VB"
        else -> label.trim().uppercase()
    }

    fun canonicalLeagueFor(label: String): String = normalizeLeague(label)

    /** Provider leagues represented by a UI aggregate. */
    fun scheduleLeaguesFor(label: String): Set<String> = when (normalizeLeague(label)) {
        "WRESTLING" -> setOf("WWE", "AEW", "TNA", "AAA WRESTLING")
        else -> setOf(normalizeLeague(label))
    }

    val uiLeagueChoices: List<String> = uiChoices

    suspend fun load(): List<SportsEvent> {
        ScheduleEngine.start()
        if (ScheduleEngine.state.value.events.isEmpty()) ScheduleEngine.refreshNow()
        return ScheduleEngine.state.value.events
    }

    suspend fun loadBackground(): List<SportsEvent> {
        ScheduleEngine.start()
        if (ScheduleEngine.state.value.events.isEmpty()) ScheduleEngine.refreshNow()
        return ScheduleEngine.state.value.events
    }

    suspend fun loadForLeague(label: String, daysAhead: Int = 3): List<SportsEvent> {
        val events = load()
        val wanted = scheduleLeaguesFor(label)
        return events.filter { normalizeLeague(it.league) in wanted }
    }
}
