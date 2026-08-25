package com.xsportsx.app

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale
import java.util.TimeZone

private data class UpcomingTvEvent(val league: String, val away: String, val home: String, val time: String, val network: String)

private fun upcomingTvDateRange(): String {
    val fmt = SimpleDateFormat("yyyyMMdd", Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") }
    val cal = Calendar.getInstance(TimeZone.getTimeZone("UTC"))
    return buildString {
        append(fmt.format(cal.time))
        cal.add(Calendar.DAY_OF_YEAR, 1)
        append('-')
        append(fmt.format(cal.time))
    }
}

private suspend fun loadUpcomingTvEvents(): List<UpcomingTvEvent> = withContext(Dispatchers.IO) {
    liveLeagues.flatMap { league ->
        val connection = runCatching {
            URL("https://site.api.espn.com/apis/site/v2/sports/${league.sport}/${league.id}/scoreboard?dates=${upcomingTvDateRange()}&limit=25").openConnection() as HttpURLConnection
        }.getOrNull() ?: return@flatMap emptyList()
        runCatching {
            connection.connectTimeout = 2500
            connection.readTimeout = 4500
            connection.setRequestProperty("User-Agent", "XSportsX/1.6")
            val root = if (connection.responseCode in 200..299) connection.inputStream.bufferedReader().use { JSONObject(it.readText()) } else null
            val events = root?.optJSONArray("events") ?: return@runCatching emptyList<UpcomingTvEvent>()
            buildList {
                for (i in 0 until events.length()) {
                    val event = events.optJSONObject(i) ?: continue
                    val competition = event.optJSONArray("competitions")?.optJSONObject(0) ?: continue
                    val status = competition.optJSONObject("status")?.optJSONObject("type") ?: continue
                    if (status.optString("state") != "pre") continue
                    val competitors = competition.optJSONArray("competitors") ?: continue
                    var away = "TBD"
                    var home = "TBD"
                    for (j in 0 until competitors.length()) {
                        val team = competitors.optJSONObject(j) ?: continue
                        val name = team.optJSONObject("team")?.optString("abbreviation").orEmpty().ifBlank { "TBD" }
                        if (team.optString("homeAway") == "home") home = name else away = name
                    }
                    val date = event.optString("date")
                    val time = runCatching {
                        val instant = java.time.Instant.parse(date)
                        val fmt = SimpleDateFormat("h:mm a", Locale.US)
                        fmt.timeZone = TimeZone.getDefault()
                        fmt.format(java.util.Date.from(instant))
                    }.getOrDefault("TBD")
                    val network = competition.optJSONArray("broadcasts")?.optJSONObject(0)?.optJSONArray("names")?.optString(0).orEmpty().ifBlank { "TBD" }
                    add(UpcomingTvEvent(league.name, away, home, time, network))
                }
            }
        }.getOrDefault(emptyList()).also { connection.disconnect() }
    }.take(30)
}

@Composable
fun TvUpcomingPanel() {
    var events by remember { mutableStateOf<List<UpcomingTvEvent>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    LaunchedEffect(Unit) {
        events = runCatching { loadUpcomingTvEvents() }.getOrDefault(emptyList())
        loading = false
    }
    if (loading) {
        TvEmpty("LOADING UPCOMING EVENTS…")
    } else if (events.isEmpty()) {
        TvEmpty("NO UPCOMING EVENTS FOUND")
    } else {
        LazyRow(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            items(events) { event -> UpcomingTvCard(event) }
        }
    }
}

@Composable
private fun UpcomingTvCard(event: UpcomingTvEvent) {
    Column(
        Modifier.width(210.dp).height(140.dp).background(Color(0xFF0B111A), RoundedCornerShape(14.dp)).border(1.dp, Color(0xFFFF1838).copy(alpha = .24f), RoundedCornerShape(14.dp)).padding(14.dp)
    ) {
        Row(Modifier.fillMaxWidth()) {
            Text(event.league, color = Color(0xFFFF1838), fontSize = 9.sp)
            Spacer(Modifier.weight(1f))
            Text(event.time, color = Color.White, fontSize = 9.sp)
        }
        Spacer(Modifier.height(12.dp))
        Text("${event.away} @ ${event.home}", color = Color.White, fontSize = 16.sp)
        Spacer(Modifier.height(8.dp))
        Text(event.network, color = Color(0xFF8993A2), fontSize = 9.sp)
    }
}
