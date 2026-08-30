package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Fast per-league schedule path.
 *
 * IMPORTANT: use the same complete provider chain as the global schedule service.
 * The previous implementation routed league screens through ReliableLeagueScheduleFallback,
 * which is intentionally smaller and caused valid leagues such as MLB/WNBA to appear empty.
 * Keeping the call per-league still isolates the selected league without sacrificing providers.
 */
object FastLeagueScheduleLoader {
    suspend fun load(league: String, daysAhead: Int = 3): List<SportsEvent> = withContext(Dispatchers.IO) {
        SportsScheduleService.loadForLeague(
            SportsScheduleService.canonicalLeagueFor(league),
            daysAhead.coerceIn(0, 3)
        )
    }
}
