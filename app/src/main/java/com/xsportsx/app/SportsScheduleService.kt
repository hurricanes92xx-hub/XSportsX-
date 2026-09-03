package com.xsportsx.app

/** Canonical schedule facade used by Mobile and TV. */
object SportsScheduleService {
    private val uiChoices = listOf(
        "NFL", "NBA", "WNBA", "NCAA FB", "NCAA FCS", "NCAA BB", "NCAA WBB", "MLB", "NCAA BASEBALL", "NHL",
        "NCAA MEN HOCKEY", "NCAA WOMEN HOCKEY", "NCAA SOFTBALL", "NCAA VB", "NCAA MEN SOCCER", "NCAA WOMEN SOCCER",
        "NCAA MEN LAX", "NCAA WOMEN LAX", "MLS", "EPL", "LaLiga", "Bundesliga", "Serie A", "Ligue 1", "UCL", "UEL", "NWSL",
        "UFC", "BOXING"
    )

    /** One identity for every common provider/UI spelling. */
    fun normalizeLeague(label: String): String {
        val value = label.trim().uppercase().replace(Regex("\\s+"), " ")
        return when (value) {
            "COLLEGE FOOTBALL", "COLLEGE FOOTBALL FBS", "NCAA FOOTBALL", "NCAAF", "NCAA FBS",
            "NCAA FBS FOOTBALL", "NCAA DIVISION I FOOTBALL", "NCAA DIVISION I FBS FOOTBALL",
            "NCAA D1 FOOTBALL", "NCAA FB" -> "NCAA FB"
            "COLLEGE FCS", "COLLEGE FOOTBALL FCS", "NCAA FOOTBALL CHAMPIONSHIP", "NCAA FCS FOOTBALL", "NCAA FCS" -> "NCAA FCS"
            "COLLEGE BASKETBALL", "NCAA MEN", "NCAAM", "NCAA MEN'S BASKETBALL", "NCAA MEN BASKETBALL" -> "NCAA BB"
            "NCAA WOMEN", "NCAAW", "NCAA WOMEN'S BASKETBALL", "NCAA WOMEN BASKETBALL" -> "NCAA WBB"
            "COLLEGE BASEBALL", "NCAA BASEBALL" -> "NCAA BASEBALL"
            "COLLEGE SOFTBALL", "NCAA SOFTBALL" -> "NCAA SOFTBALL"
            "COLLEGE MEN'S HOCKEY", "NCAA MEN'S HOCKEY", "NCAA MEN HOCKEY" -> "NCAA MEN HOCKEY"
            "COLLEGE WOMEN'S HOCKEY", "NCAA WOMEN'S HOCKEY", "NCAA WOMEN HOCKEY" -> "NCAA WOMEN HOCKEY"
            "COLLEGE MEN'S SOCCER", "NCAA MEN'S SOCCER", "NCAA MEN SOCCER" -> "NCAA MEN SOCCER"
            "COLLEGE WOMEN'S SOCCER", "NCAA WOMEN'S SOCCER", "NCAA WOMEN SOCCER" -> "NCAA WOMEN SOCCER"
            "COLLEGE WOMEN'S LACROSSE", "NCAA WOMEN'S LACROSSE", "NCAA WOMEN LAX" -> "NCAA WOMEN LAX"
            "COLLEGE MEN'S LACROSSE", "NCAA MEN'S LACROSSE", "NCAA MEN LAX" -> "NCAA MEN LAX"
            "NCAA VOLLEYBALL", "COLLEGE VOLLEYBALL", "NCAA VB", "NCAA WOMEN'S VOLLEYBALL", "NCAA MEN'S VOLLEYBALL" -> "NCAA VB"
            else -> value
        }
    }

    fun canonicalLeagueFor(label: String): String = normalizeLeague(label)
    val uiLeagueChoices: List<String> = uiChoices

    /** All schedule callers use the same repository, including direct fallbacks. */
    suspend fun load(): List<SportsEvent> = ScheduleSnapshotRepository.all(false)
    suspend fun loadBackground(): List<SportsEvent> = ScheduleSnapshotRepository.all(false)
    suspend fun loadForLeague(label: String, daysAhead: Int = 3): List<SportsEvent> =
        ScheduleSnapshotRepository.upcoming(normalizeLeague(label), false)
}
