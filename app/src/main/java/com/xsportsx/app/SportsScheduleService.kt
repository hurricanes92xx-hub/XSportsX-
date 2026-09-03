package com.xsportsx.app

/**
 * Canonical schedule facade used by Mobile and TV.
 *
 * All schedule data now comes from the repository-refreshed canonical feed.
 * Keeping this object as the public facade avoids duplicate schedule clients
 * scattered through the UI while preserving the league normalization API.
 */
object SportsScheduleService {
    private val uiChoices = listOf(
        "NFL", "NBA", "WNBA", "NCAA FB", "NCAA FCS", "NCAA BB", "NCAA WBB", "MLB", "NCAA BASEBALL", "NHL",
        "NCAA MEN HOCKEY", "NCAA WOMEN HOCKEY", "NCAA SOFTBALL", "NCAA VB", "NCAA MEN SOCCER", "NCAA WOMEN SOCCER",
        "NCAA MEN LAX", "NCAA WOMEN LAX", "MLS", "EPL", "LaLiga", "Bundesliga", "Serie A", "Ligue 1", "UCL", "UEL", "NWSL",
        "UFC", "BOXING"
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

    val uiLeagueChoices: List<String> = uiChoices

    suspend fun load(): List<SportsEvent> = CanonicalScheduleProvider.load(null, 3)

    suspend fun loadBackground(): List<SportsEvent> = CanonicalScheduleProvider.load(null, 7)

    suspend fun loadForLeague(label: String, daysAhead: Int = 3): List<SportsEvent> =
        CanonicalScheduleProvider.load(normalizeLeague(label), daysAhead.coerceIn(1, 7))
}
