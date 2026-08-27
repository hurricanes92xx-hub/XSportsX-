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
    val isLive: Boolean
        get() = state.equals("in", true) || state.equals("live", true) || status.contains("live", true) || status.contains("in progress", true)

    /** True only for scheduled events beginning within the next 30 minutes. */
    fun isPregame(nowMillis: Long = System.currentTimeMillis()): Boolean {
        val start = runCatching { java.time.Instant.parse(startUtc).toEpochMilli() }.getOrDefault(0L)
        return start > nowMillis && start <= nowMillis + 30L * 60L * 1000L && !isLive
    }

    val isUpcoming: Boolean
        get() = !isLive && (state.equals("pre", true) || state.equals("scheduled", true) || state.isBlank() || status.contains("upcoming", true) || status.contains("scheduled", true))
}
