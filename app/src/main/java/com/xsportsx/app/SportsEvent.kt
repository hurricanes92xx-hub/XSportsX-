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

    /** Confidence score (0-100) for the current LIVE/UPCOMING classification. */
    val lifecycleConfidence: Int
        get() = EventLifecycleResolver.confidence(this)

    fun isPregame(nowMillis: Long = System.currentTimeMillis()): Boolean =
        EventLifecycleResolver.isPregame(this, nowMillis)

    val isUpcoming: Boolean
        get() = EventLifecycleResolver.isUpcoming(this)
}
