package com.xsportsx.app

/** Official-first YouTube live discovery targets for scheduled sports events. */
data class YouTubeLiveTarget(
    val sport: String,
    val leagueAliases: List<String>,
    val channelNames: List<String>,
    val channelUrls: List<String> = emptyList(),
    val queryAliases: List<String> = emptyList()
)

object YouTubeLiveSearchCatalog {
    val targets: List<YouTubeLiveTarget> = listOf(
        YouTubeLiveTarget(
            sport = "Football",
            leagueAliases = listOf("NFL"),
            channelNames = listOf("NFL", "ESPN", "ESPN Deportes", "FOX Sports", "CBS Sports", "NBC Sports", "NFL Network"),
            queryAliases = listOf("NFL live", "football live")
        ),
        YouTubeLiveTarget(
            sport = "Basketball",
            leagueAliases = listOf("NBA", "WNBA", "NCAA BB", "NCAA WBB"),
            channelNames = listOf("NBA", "WNBA", "ESPN", "ESPN2", "ABC", "TNT Sports", "NBA TV", "CBS Sports", "FOX Sports"),
            queryAliases = listOf("basketball live")
        ),
        YouTubeLiveTarget(
            sport = "Baseball",
            leagueAliases = listOf("MLB", "NCAA BASEBALL"),
            channelNames = listOf("MLB", "ESPN", "FOX Sports", "TBS", "MLB Network", "CBS Sports"),
            queryAliases = listOf("baseball live")
        ),
        YouTubeLiveTarget(
            sport = "Hockey",
            leagueAliases = listOf("NHL"),
            channelNames = listOf("NHL", "ESPN", "ABC", "TNT Sports"),
            queryAliases = listOf("hockey live")
        ),
        YouTubeLiveTarget(
            sport = "Soccer",
            leagueAliases = listOf("MLS", "EPL", "LaLiga", "Bundesliga", "Serie A", "Ligue 1", "UCL", "UEL", "NWSL"),
            channelNames = listOf("MLS", "Premier League", "UEFA", "ESPN", "CBS Sports", "FOX Sports", "FIFA"),
            queryAliases = listOf("soccer live", "football live")
        ),
        YouTubeLiveTarget(
            sport = "Motorsports",
            leagueAliases = listOf("MONSTER JAM", "MONSTERJAM"),
            channelNames = listOf("Monster Jam"),
            channelUrls = listOf("https://www.youtube.com/@MonsterJam/streams"),
            queryAliases = listOf("Monster Jam live", "Monster Jam event live", "Monster Jam livestream")
        ),
        YouTubeLiveTarget(
            sport = "MMA",
            leagueAliases = listOf("UFC"),
            channelNames = listOf("UFC", "ESPN", "ESPN MMA"),
            queryAliases = listOf("UFC live")
        ),
        YouTubeLiveTarget(
            sport = "Boxing",
            leagueAliases = listOf("BOXING"),
            channelNames = listOf("Top Rank Boxing", "Premier Boxing Champions", "DAZN Boxing", "ESPN Boxing"),
            queryAliases = listOf("boxing live")
        )
    )

    fun forLeague(league: String): YouTubeLiveTarget? =
        targets.firstOrNull { target -> target.leagueAliases.any { it.equals(league.trim(), ignoreCase = true) } }

    fun queries(league: String, home: String, away: String): List<String> {
        val target = forLeague(league) ?: return listOf("$away vs $home live", "$league $away $home live")
        val matchup = listOf("$away vs $home live", "$away $home live", "$league $away $home live")
        val generic = target.queryAliases
        return (matchup + generic + target.channelNames.flatMap { listOf("$it $away $home live", "$it $league live") }).distinct()
    }
}
