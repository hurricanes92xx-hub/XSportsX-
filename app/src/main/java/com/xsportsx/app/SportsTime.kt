package com.xsportsx.app

import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/**
 * Single timezone boundary for schedule presentation.
 * Schedule data stays UTC; only the UI converts it to the device timezone.
 */
object SportsTime {
    private val displayFormatter = DateTimeFormatter
        .ofPattern("EEE, M/d • h:mm a", Locale.US)
        .withZone(ZoneId.systemDefault())

    private val compactFormatter = DateTimeFormatter
        .ofPattern("M/d • h:mm a", Locale.US)
        .withZone(ZoneId.systemDefault())

    fun formatForViewer(startUtc: String): String = runCatching {
        displayFormatter.format(Instant.parse(startUtc))
    }.getOrElse { "TIME TBD" }

    fun formatCompactForViewer(startUtc: String): String = runCatching {
        compactFormatter.format(Instant.parse(startUtc))
    }.getOrElse { "UPCOMING" }

    fun viewerZone(): ZoneId = ZoneId.systemDefault()
}
