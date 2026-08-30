package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Fast league-screen facade. The canonical server-refreshed feed is the first
 * source; SportsScheduleService retains direct ESPN/NCAA recovery when needed.
 */
object FastLeagueScheduleLoader {
    suspend fun load(league: String, daysAhead: Int = 3): List<SportsEvent> = withContext(Dispatchers.IO) {
        val canonical = SportsScheduleService.canonicalLeagueFor(league)
        val feed = CanonicalScheduleProvider.load(canonical, daysAhead)
        if (feed.isNotEmpty()) return@withContext feed
        SportsScheduleService.loadForLeague(league, daysAhead)
    }
}
