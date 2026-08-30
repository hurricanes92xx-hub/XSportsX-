package com.xsportsx.app

import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit

/**
 * Live data must not wait for the 30-minute canonical-feed refresh.
 * Pull today's scoreboard directly from the reliable per-league recovery path.
 */
object FreshLiveScheduleProvider {
    suspend fun load(): List<SportsEvent> = coroutineScope {
        val limiter = Semaphore(8)
        val results = SportsScheduleService.uiLeagueChoices.map { league ->
            async {
                limiter.withPermit {
                    runCatching { ReliableLeagueScheduleFallback.load(league, 0) }
                        .getOrDefault(emptyList())
                }
            }
        }.awaitAll().flatten()

        val monsterJam = runCatching { MonsterJamLiveResolver.loadLive() }.getOrDefault(emptyList())
        (results + monsterJam)
            .filter { it.isLive }
            .map { it.copy(league = SportsScheduleService.canonicalLeagueFor(it.league)) }
            .distinctBy { it.id.ifBlank { "${it.league}|${it.away}|${it.home}|${it.startUtc}" } }
            .sortedWith(compareBy<SportsEvent> { it.league.lowercase() }.thenBy { it.startUtc })
    }
}
