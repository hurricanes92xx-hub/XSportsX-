package com.xsportsx.app

import androidx.compose.foundation.background
import androidx.compose.foundation.basicMarquee
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.supervisorScope
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale
import java.util.TimeZone

data class TickerItem(val kind:String,val league:String,val text:String,val timestamp:Long=0L)
data class TickerLeague(val name:String,val sport:String,val id:String)
data class TickerLeagueGroup(val league:String,val items:List<TickerItem>)

private val tickerLeagues=listOf(
    TickerLeague("NFL","football","nfl"),TickerLeague("NCAA FB","football","college-football"),
    TickerLeague("NBA","basketball","nba"),TickerLeague("WNBA","basketball","wnba"),
    TickerLeague("NCAA BB","basketball","mens-college-basketball"),TickerLeague("MLB","baseball","mlb"),
    TickerLeague("NHL","hockey","nhl"),TickerLeague("MLS","soccer","usa.1"),
    TickerLeague("EPL","soccer","eng.1"),TickerLeague("UCL","soccer","uefa.champions"),
    TickerLeague("LaLiga","soccer","esp.1"),TickerLeague("Serie A","soccer","ita.1"),
    TickerLeague("Bundesliga","soccer","ger.1"),TickerLeague("Ligue 1","soccer","fra.1")
)

private fun todayUtc():String=SimpleDateFormat("yyyyMMdd",Locale.US).apply{timeZone=TimeZone.getTimeZone("UTC")}.format(Calendar.getInstance(TimeZone.getTimeZone("UTC")).time)

private suspend fun getJson(url:String):JSONObject?=withContext(Dispatchers.IO){
    withTimeoutOrNull(5500L){
        val c=runCatching{URL(url).openConnection() as HttpURLConnection}.getOrNull()?:return@withTimeoutOrNull null
        try{
            c.connectTimeout=2500;c.readTimeout=4500;c.requestMethod="GET";c.instanceFollowRedirects=true
            c.setRequestProperty("User-Agent","XSportsX/1.9 Android");c.setRequestProperty("Accept","application/json")
            if(c.responseCode !in 200..299)null else runCatching{JSONObject(c.inputStream.bufferedReader().use{it.readText()})}.getOrNull()
        }catch(_:Exception){null}finally{c.disconnect()}
    }
}

private fun eventTime(e:JSONObject):Long=runCatching{java.time.Instant.parse(e.optString("date")).toEpochMilli()}.getOrDefault(0L)

private suspend fun loadLeague(l:TickerLeague):TickerLeagueGroup?{
    val root=getJson("https://site.api.espn.com/apis/site/v2/sports/${l.sport}/${l.id}/scoreboard?dates=${todayUtc()}&limit=100")?:return null
    val events=root.optJSONArray("events")?:return TickerLeagueGroup(l.name,emptyList())
    val now=System.currentTimeMillis()
    val items=buildList{
        for(i in 0 until events.length()){
            val e=events.optJSONObject(i)?:continue
            val comp=e.optJSONArray("competitions")?.optJSONObject(0)?:continue
            val teams=comp.optJSONArray("competitors")?:continue
            var home="TBD";var away="TBD";var hs="";var ascore=""
            for(j in 0 until teams.length()){
                val c=teams.optJSONObject(j)?:continue
                val t=c.optJSONObject("team")
                val name=t?.optString("abbreviation")?.ifBlank{t.optString("shortDisplayName")}.orEmpty().ifBlank{c.optString("displayName").ifBlank{"TBD"}}
                if(c.optString("homeAway")=="home"){home=name;hs=c.optString("score")}else{away=name;ascore=c.optString("score")}
            }
            val type=comp.optJSONObject("status")?.optJSONObject("type")
            val state=type?.optString("state").orEmpty();val detail=type?.optString("shortDetail").orEmpty();val ts=eventTime(e)
            val kind=when(state){"in"->"LIVE";"post"->"FINAL";else->"UPCOMING"}
            if(ts==0L||ts>=now-36L*60L*60L*1000L){
                val text=if(kind=="UPCOMING")"$away @ $home${detail.takeIf{it.isNotBlank()}?.let{" • $it"}?:""}"
                else "$away $ascore • $home $hs${detail.takeIf{it.isNotBlank()}?.let{" • $it"}?:""}"
                add(TickerItem(kind,l.name,text,ts))
            }
        }
    }
    return TickerLeagueGroup(l.name,items.sortedWith(compareBy<TickerItem>{if(it.kind=="LIVE")0 else if(it.kind=="UPCOMING")1 else 2}.thenBy{it.timestamp}).take(12))
}

private suspend fun loadTickerGroups():List<TickerLeagueGroup>=supervisorScope{
    // All leagues are isolated. A slow/broken league cannot block every other league.
    tickerLeagues.map{l->async{runCatching{loadLeague(l)}.getOrNull()}}.awaitAll()
        .filterNotNull().filter{it.items.isNotEmpty()}
        .sortedBy{if(it.items.any{item->item.kind=="LIVE"})0 else 1}
}

private fun line(g:TickerLeagueGroup)=g.items.joinToString("     •     "){ "${it.kind}  ${it.text}" }

@Composable
fun HomeSportsTicker(modifier:Modifier=Modifier){
    var groups by remember{mutableStateOf<List<TickerLeagueGroup>>(emptyList())}
    var index by remember{mutableIntStateOf(0)}
    var loading by remember{mutableStateOf(true)}
    var failed by remember{mutableStateOf(false)}
    LaunchedEffect(Unit){
        while(isActive){
            loading=true
            val loaded=runCatching{loadTickerGroups()}.getOrDefault(emptyList())
            if(loaded.isNotEmpty()){groups=loaded;index=0;failed=false}else if(groups.isEmpty())failed=true
            loading=false;delay(60_000L)
        }
    }
    LaunchedEffect(groups.size){while(isActive&&groups.size>1){delay(7_000L);index=(index+1)%groups.size}}
    val group=groups.getOrNull(index.coerceIn(0,(groups.size-1).coerceAtLeast(0)))
    val text=group?.let(::line)?.takeIf{it.isNotBlank()}?:when{
        loading&&groups.isEmpty()->"LIVE SCORES • CONNECTING TO SPORTS FEEDS…"
        failed->"SPORTS FEED • NO CURRENT SCORES AVAILABLE"
        else->"SPORTS FEED • NO LIVE GAMES RIGHT NOW"
    }
    Box(modifier.fillMaxWidth().height(64.dp).background(Color(0xF2080A10)),contentAlignment=Alignment.CenterStart){
        Row(Modifier.fillMaxSize(),verticalAlignment=Alignment.CenterVertically){
            Box(Modifier.padding(start=10.dp,end=8.dp).clip(RoundedCornerShape(8.dp)).background(Color(0xFF111722)).padding(horizontal=11.dp,vertical=8.dp)){Text("X",color=Color(0xFFFF1744),fontSize=20.sp,fontWeight=FontWeight.Black)}
            Text(group?.league?:"SPORTS",color=Color.White,fontSize=11.sp,fontWeight=FontWeight.Black,modifier=Modifier.padding(end=10.dp))
            Box(Modifier.weight(1f).padding(end=12.dp).clip(RoundedCornerShape(8.dp)).background(Color(0xFF0D1118)).padding(horizontal=10.dp,vertical=9.dp)){
                Text(text,color=Color(0xFFE5E9F0),fontSize=12.sp,fontWeight=FontWeight.SemiBold,maxLines=1,modifier=Modifier.fillMaxWidth().basicMarquee())
            }
        }
    }
}
