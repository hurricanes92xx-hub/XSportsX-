package com.xsportsx.app

/** Canonical schedule event model shared by schedule UI, matchers and players. */
data class SportsEvent(
    val id: String,
    val sport: String,
    val league: String,
    val title: String,
    val startUtc: String,
    val status: String = "",
    val state: String = "",
    val home: String = "",
    val away: String = "",
    val homeLogo: String = "",
    val awayLogo: String = "",
    val broadcast: String = "",
    val artUrl: String = "",
    val sourceUrl: String = "",
    val youtubeVideoId: String = ""
) {
    val lifecycle: EventLifecycle
        get() = EventLifecycleResolver.resolve(this)

    val isLive: Boolean
        get() = EventLifecycleResolver.isLive(this)

    fun isPregame(nowMillis: Long = System.currentTimeMillis()): Boolean {
        val start = runCatching { java.time.Instant.parse(startUtc).toEpochMilli() }.getOrDefault(0L)
        return start > nowMillis && start <= nowMillis + 30L * 60L * 1000L &&
            lifecycle == EventLifecycle.PREGAME
    }

    val isUpcoming: Boolean
        get() {
            val start = runCatching { java.time.Instant.parse(startUtc).toEpochMilli() }.getOrDefault(0L)
            val now = System.currentTimeMillis()
            return lifecycle in setOf(EventLifecycle.PREGAME, EventLifecycle.SCHEDULED) &&
                start > now && start <= now + 3L * 24L * 60L * 60L * 1000L
        }
}
