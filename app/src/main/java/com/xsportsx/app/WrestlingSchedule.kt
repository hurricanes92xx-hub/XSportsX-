package com.xsportsx.app

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp


data class WrestlingEvent(val brand:String,val title:String,val date:String,val location:String,val kind:String,val time:String="")

private val fallbackWrestlingEvents = listOf(
    WrestlingEvent("WWE","NXT Heatwave","AUG 30, 2026","Edinburg, TX","SPECIAL","1:00 PM ET"),
    WrestlingEvent("WWE","Sunday Night's Main Event","SEP 6, 2026","Atlanta, GA","SPECIAL","8:00 PM ET"),
    WrestlingEvent("WWE","Worlds Collide","SEP 26, 2026","Chicago, IL","SPECIAL","8:00 PM ET"),
    WrestlingEvent("WWE","Money in the Bank","OCT 10, 2026","New Orleans, LA","PLE","6:00 PM ET"),
    WrestlingEvent("WWE","Survivor Series: WarGames","NOV 28, 2026","Houston, TX","PLE","6:00 PM ET"),
    WrestlingEvent("AEW","All In: London","AUG 30, 2026","London, England","PPV","4:30 PM UK"),
    WrestlingEvent("AEW","All Out","SEP 26, 2026","Chicago, IL","PPV","6:00 PM CT"),
    WrestlingEvent("AEW","Grand Slam: France","OCT 6, 2026","Paris, France","SPECIAL","TBA"),
    WrestlingEvent("AEW","WrestleDream","OCT 17, 2026","Orlando, FL","PPV","7:00 PM ET"),
    WrestlingEvent("AEW","Full Gear","NOV 14, 2026","Phoenix, AZ","PPV","4:00 PM PT"),
    WrestlingEvent("TNA","Bound for Glory","OCT 11, 2026","Tampa, FL","PPV","4:00 PM Local")
)

private val wrestlingWeekly = listOf(
    "WWE RAW • Mondays",
    "WWE NXT • Tuesdays",
    "WWE Evolve • Wednesdays",
    "WWE Main Event • Thursdays",
    "WWE SmackDown • Fridays",
    "AEW Dynamite • Wednesdays",
    "AEW Collision • Saturdays",
    "TNA iMPACT! • Thursdays"
)

private fun remoteWrestlingEvents(games: List<Game>): List<WrestlingEvent> = games.filter { it.league in setOf("WWE","AEW","TNA") }.map {
    WrestlingEvent(
        brand = it.league,
        title = it.matchup,
        date = it.time.substringBefore(" • ").ifBlank { "UPCOMING" },
        location = "",
        kind = it.tag,
        time = it.time.substringAfter(" • ", it.time)
    )
}

@Composable
fun WrestlingScheduleSection(onWatch:()->Unit={}) {
    val context = androidx.compose.ui.platform.LocalContext.current
    var wrestlingEvents by remember { mutableStateOf(fallbackWrestlingEvents) }
    LaunchedEffect(Unit) {
        while (true) {
            val remote = runCatching { ScheduleFeed.load(context) }.getOrDefault(emptyList())
            val mapped = remoteWrestlingEvents(remote)
            if (mapped.isNotEmpty()) wrestlingEvents = mapped
            kotlinx.coroutines.delay(6L * 60L * 60L * 1000L)
        }
    }
    Column(Modifier.fillMaxWidth()) {
        Row(verticalAlignment=Alignment.CenterVertically) {
            Text("WRESTLING",color=Color.White,fontSize=15.sp,fontWeight=FontWeight.Black,letterSpacing=1.4.sp)
            Spacer(Modifier.width(8.dp))
            Text("WWE • AEW • TNA",color=Color(0xFF727B8B),fontSize=8.sp,fontWeight=FontWeight.Black,letterSpacing=.8.sp)
        }
        Spacer(Modifier.height(9.dp))
        Row(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
            listOf("WWE" to Color(0xFF2E8BFF),"AEW" to Color(0xFFFF102F),"TNA" to Color(0xFFFF6D00)).forEach { (brand,color) ->
                Box(Modifier.clip(RoundedCornerShape(10.dp)).background(color.copy(alpha=.16f)).padding(horizontal=9.dp,vertical=6.dp)) { Text(brand,color=color,fontSize=9.sp,fontWeight=FontWeight.Black) }
            }
        }
        Spacer(Modifier.height(9.dp))
        LazyRow(horizontalArrangement=Arrangement.spacedBy(10.dp),contentPadding=PaddingValues(end=8.dp)) {
            items(wrestlingEvents,key={"${it.brand}-${it.title}"}) { event -> WrestlingEventCard(event,onWatch) }
        }
        Spacer(Modifier.height(10.dp))
        Text("WEEKLY",color=Color(0xFF727B8B),fontSize=8.sp,fontWeight=FontWeight.Black,letterSpacing=1.sp)
        Spacer(Modifier.height(6.dp))
        LazyRow(horizontalArrangement=Arrangement.spacedBy(7.dp),contentPadding=PaddingValues(end=8.dp)) {
            items(wrestlingWeekly) { Text(it,color=Color(0xFFDCE1E9),fontSize=9.sp,fontWeight=FontWeight.Bold,modifier=Modifier.clip(RoundedCornerShape(9.dp)).background(Color(0xFF141A24)).padding(horizontal=9.dp,vertical=7.dp)) }
        }
    }
}

@Composable private fun WrestlingEventCard(event:WrestlingEvent,onWatch:()->Unit) {
    val brandColor=when(event.brand){"WWE"->Color(0xFF2E8BFF);"AEW"->Color(0xFFFF102F);else->Color(0xFFFF6D00)}
    Column(Modifier.width(178.dp).height(154.dp).clip(RoundedCornerShape(17.dp)).background(Color(0xFF0D1119)).clickable{onWatch()}.padding(12.dp)) {
        Row(verticalAlignment=Alignment.CenterVertically) {
            Text(event.brand,color=brandColor,fontSize=9.sp,fontWeight=FontWeight.Black)
            Spacer(Modifier.weight(1f))
            Text(event.kind,color=Color(0xFF8F98A7),fontSize=7.sp,fontWeight=FontWeight.Black)
        }
        Spacer(Modifier.height(9.dp))
        Text(event.title,color=Color.White,fontSize=14.sp,fontWeight=FontWeight.Black,maxLines=2,overflow=TextOverflow.Ellipsis)
        Spacer(Modifier.height(7.dp))
        Text(event.date,color=brandColor,fontSize=10.sp,fontWeight=FontWeight.Black)
        Text(event.location,color=Color(0xFF9BA4B2),fontSize=9.sp,maxLines=1,overflow=TextOverflow.Ellipsis)
        if(event.time.isNotBlank()) Text(event.time,color=Color(0xFF727B8B),fontSize=8.sp,fontWeight=FontWeight.Bold)
        Spacer(Modifier.weight(1f))
        Text("FIND STREAM →",color=Color.White,fontSize=8.sp,fontWeight=FontWeight.Black)
    }
}
