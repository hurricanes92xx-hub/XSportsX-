package com.xsportsx.app

import androidx.compose.foundation.background
import androidx.compose.foundation.basicMarquee
import androidx.compose.foundation.layout.*
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import java.time.Instant
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

data class TickerItem(val kind: String, val league: String, val text: String, val timestamp: Long = 0L)
data class TickerLeague(val name: String, val sport: String, val id: String)
data class TickerLeagueGroup(val league: String, val items: List<TickerItem>)

private const val TICKER_REFRESH_MS = 60_000L

private fun tickerTime(startUtc: String): Long = runCatching { Instant.parse(startUtc).toEpochMilli() }.getOrDefault(0L)

private fun buildTickerGroups(events: List<SportsEvent>): List<TickerLeagueGroup> =
    events.groupBy { it.league }
        .map { (league, games) ->
            val items = games.sortedWith(compareBy<SportsEvent> { !it.isLive }.thenBy { it.startUtc }).take(8).map { event ->
                val kind = if (event.isLive) "LIVE" else "UPCOMING"
                val detail = if (event.isLive) event.status.ifBlank { "LIVE" } else formatTickerTime(event.startUtc)
                TickerItem(kind, league, "${event.away.ifBlank { "TBD" }} @ ${event.home.ifBlank { "TBD" }} • $detail", tickerTime(event.startUtc))
            }
            TickerLeagueGroup(league, items)
        }
        .filter { it.items.isNotEmpty() }
        .sortedWith(compareBy<TickerLeagueGroup> { if (it.items.any { item -> item.kind == "LIVE" }) 0 else 1 }.thenBy { it.league })

private fun formatTickerTime(startUtc: String): String = runCatching {
    SimpleDateFormat("M/d • h:mm a", Locale.US).apply { timeZone = TimeZone.getDefault() }.format(Date.from(Instant.parse(startUtc)))
}.getOrElse { "UPCOMING" }

@Composable
fun HomeSportsTicker(modifier: Modifier = Modifier, enabled: Boolean = true) {
    var groups by remember { mutableStateOf<List<TickerLeagueGroup>>(emptyList()) }
    var index by remember { mutableIntStateOf(0) }
    var loading by remember { mutableStateOf(true) }

    LaunchedEffect(enabled) {
        if (!enabled) {
            loading = false
            return@LaunchedEffect
        }
        while (isActive) {
            val loaded = runCatching {
                val upcoming = ScheduleSnapshotRepository.upcoming()
                val live = ScheduleSnapshotRepository.live()
                buildTickerGroups((live + upcoming).distinctBy { "${it.league}|${it.away}|${it.home}|${it.startUtc.take(16)}" })
            }.getOrDefault(emptyList())
            if (loaded.isNotEmpty()) {
                groups = loaded
                index = index.coerceIn(0, loaded.lastIndex)
            }
            loading = false
            delay(TICKER_REFRESH_MS)
        }
    }

    val group = groups.getOrNull(index.coerceIn(0, (groups.size - 1).coerceAtLeast(0)))
    val text = group?.items?.joinToString("     •     ") { "${it.kind} [${it.league}] ${it.text}" }
        ?: if (loading) "SPORTS FEED • LOADING" else "SPORTS FEED • NO GAMES AVAILABLE"

    Row(
        modifier.fillMaxWidth().height(42.dp).background(Color(0xEE07090E)).padding(horizontal = 18.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text("X", color = Color(0xFFFF1744), fontWeight = FontWeight.Black, fontSize = 20.sp)
        Spacer(Modifier.width(10.dp))
        Text(
            text,
            modifier = Modifier.weight(1f).basicMarquee(iterations = 1, repeatDelayMillis = 0, initialDelayMillis = 450, velocity = 45.dp),
            color = Color.White,
            fontWeight = FontWeight.Bold,
            fontSize = 12.sp,
            maxLines = 1
        )
    }

    LaunchedEffect(text) {
        if (groups.size > 1) {
            delay(8_000L)
            index = (index + 1) % groups.size
        }
    }
}
