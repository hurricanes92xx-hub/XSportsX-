package com.xsportsx.app

/** Legacy compatibility model for older schedule helpers still compiled with the canonical UI. */
data class Game(
    val league: String,
    val matchup: String,
    val time: String,
    val tag: String = "UPCOMING",
    val icon: String = "•"
)
