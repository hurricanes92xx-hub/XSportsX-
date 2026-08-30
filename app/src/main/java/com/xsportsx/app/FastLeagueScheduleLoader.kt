package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Direct per-league schedule path. Keeps league screens independent of the global feed. */
object FastLeagueScheduleLoader {
    suspend fun load(league: String, daysAhead: Int = 3): List<SportsEvent> = withContext(Dispatchers.IO) {
        ReliableLeagueScheduleFallback.load(
            SportsScheduleService.canonicalLeagueFor(league),
            daysAhead.coerceIn(0, 3)
        )
    }
}
