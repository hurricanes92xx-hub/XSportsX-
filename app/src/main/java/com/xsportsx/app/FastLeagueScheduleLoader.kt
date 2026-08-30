package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Shared three-day league facade. No screen performs its own provider fan-out. */
object FastLeagueScheduleLoader {
    suspend fun load(league: String, daysAhead: Int = 3): List<SportsEvent> = withContext(Dispatchers.IO) {
        val canonical = SportsScheduleService.canonicalLeagueFor(league)
        if (daysAhead <= 3) {
            ScheduleSnapshotRepository.upcoming(canonical)
        } else {
            ScheduleSnapshotRepository.all().filter { SportsScheduleService.canonicalLeagueFor(it.league) == canonical }
        }
    }
}
