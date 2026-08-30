package com.xsportsx.app

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.time.Instant
import java.util.Calendar
import java.util.Date
import java.util.Locale
import java.util.TimeZone

data class LeagueGame(val id:String,val away:String,val home:String,val start:Long,val status:String,val detail:String)
data class LeagueFeed(val sport:String,val id:String)
private val feeds=mapOf(
 "NFL" to LeagueFeed("football","nfl"), "NCAA FB" to LeagueFeed("football","college-football"),
 "NBA" to LeagueFeed("basketball","nba"), "WNBA" to LeagueFeed("basketball","wnba"),
 "NCAA BB" to LeagueFeed("basketball","mens-college-basketball"), "MLB" to LeagueFeed("baseball","mlb"),
 "NHL" to LeagueFeed("hockey","nhl"), "MLS" to LeagueFeed("soccer","usa.1"), "EPL" to LeagueFeed("soccer","eng.1"),
 "UCL" to LeagueFeed("soccer","uefa.champions"), "LaLiga" to LeagueFeed("soccer","esp.1"),
 "Serie A" to LeagueFeed("soccer","ita.1"), "Bundesliga" to LeagueFeed("soccer","ger.1"), "Ligue 1" to LeagueFeed("soccer","fra.1")
)
private fun dateKey(offset:Int):String { val c=Calendar.getInstance(TimeZone.getTimeZone("UTC")); c.add(Calendar.DAY_OF_YEAR,offset); return SimpleDateFormat("yyyyMMdd",Locale.US).format(c.time) }
private suspend fun games(feed:LeagueFeed):List<LeagueGame> = withContext(Dispatchers.IO) {
 val out=mutableListOf<LeagueGame>()
 for(d in 0..2){
  val url="https://site.api.espn.com/apis/site/v2/sports/${feed.sport}/${feed.id}/scoreboard?dates=${dateKey(d)}&limit=100"
  val body=runCatching{ val c=URL(url).openConnection() as HttpURLConnection; c.connectTimeout=3500;c.readTimeout=5500;c.requestMethod="GET";try{if(c.responseCode in 200..299)c.inputStream.bufferedReader().use{it.readText()}else null}finally{c.disconnect()} }.getOrNull() ?: continue
  val json=runCatching{JSONObject(body)}.getOrNull() ?: continue; val events=json.optJSONArray("events") ?: continue
  for(i in 0 until events.length()){
   val e=events.optJSONObject(i)?:continue; val comp=e.optJSONArray("competitions")?.optJSONObject(0)?:continue; val teams=comp.optJSONArray("competitors")?:continue
   var away="TBD";var home="TBD";for(j in 0 until teams.length()){val t=teams.optJSONObject(j)?:continue;val n=t.optJSONObject("team")?.optString("displayName").orEmpty().ifBlank{"TBD"};if(t.optString("homeAway")=="home")home=n else away=n}
   val start=runCatching{Instant.parse(e.optString("date")).toEpochMilli()}.getOrDefault(0);val ty=comp.optJSONObject("status")?.optJSONObject("type");val state=ty?.optString("state").orEmpty();val status=if(state=="in")"LIVE"else if(state=="post")"FINAL"else"UPCOMING";out+=LeagueGame(e.optString("id"),away,home,start,status,ty?.optString("shortDetail").orEmpty())
  }
 }
 out.distinctBy{it.id}.sortedBy{it.start}
}
@Composable fun LeagueScheduleScreen(league:String,onBack:()->Unit){
 val feed=feeds[league];var list by remember(league){mutableStateOf<List<LeagueGame>>(emptyList())};var loading by remember(league){mutableStateOf(true)};var error by remember(league){mutableStateOf<String?>(null)};var tab by remember(league){mutableStateOf("UPCOMING")};var streamFilter by remember{mutableStateOf<String?>(null)}
 LaunchedEffect(league){loading=true;runCatching{if(feed==null)error("League not configured")else games(feed)}.onSuccess{list=it}.onFailure{error=it.message?:"Unable to load schedule"};loading=false}
 if(streamFilter!=null){LiveChannelsScreen(filter=streamFilter,onBack={streamFilter=null});return}
 val visible=list.filter{if(tab=="LIVE")it.status=="LIVE" else it.status=="UPCOMING"}.take(100);val grouped=visible.groupBy{dayLabel(it.start)}
 Column(Modifier.fillMaxSize().background(Color(0xFF05060A))){
  Row(Modifier.fillMaxWidth().padding(20.dp),verticalAlignment=Alignment.CenterVertically){Text("‹",color=Color.White,fontSize=36.sp,modifier=Modifier.clickable{onBack()});Spacer(Modifier.width(12.dp));Column(Modifier.weight(1f)){Text(league,color=Color.White,fontSize=27.sp,fontWeight=FontWeight.Black);Text("${league} GAMES • NEXT 3 DAYS",color=Color(0xFF737B89),fontSize=10.sp,fontWeight=FontWeight.Bold)}}
  Row(Modifier.padding(horizontal=20.dp),horizontalArrangement=Arrangement.spacedBy(8.dp)){FilterChip(selected=tab=="LIVE",onClick={tab="LIVE"},label={Text("LIVE")});FilterChip(selected=tab=="UPCOMING",onClick={tab="UPCOMING"},label={Text("UPCOMING")})}
  Spacer(Modifier.height(8.dp))
  when{loading->Box(Modifier.fillMaxSize(),contentAlignment=Alignment.Center){CircularProgressIndicator(color=Color(0xFFFF1744))};error!=null->Box(Modifier.fillMaxSize(),contentAlignment=Alignment.Center){Text(error!!,color=Color.White)};visible.isEmpty()->Box(Modifier.fillMaxSize(),contentAlignment=Alignment.Center){Text(if(tab=="LIVE")"No live ${league} games right now"else"No upcoming ${league} games in the next 3 days",color=Color(0xFF858B98))};else->LazyColumn(contentPadding=PaddingValues(20.dp),verticalArrangement=Arrangement.spacedBy(10.dp)){grouped.forEach{(day,gs)->item{Text(day,color=Color.White,fontWeight=FontWeight.Black,modifier=Modifier.padding(top=8.dp))};items(gs,key={it.id}){g->Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Color(0xFF10141C)).padding(16.dp),verticalAlignment=Alignment.CenterVertically){Column(Modifier.weight(1f)){Text(g.away,color=Color.White,fontWeight=FontWeight.Bold,maxLines=1,overflow=TextOverflow.Ellipsis);Text("@ ${g.home}",color=Color(0xFFB6BDCA),fontWeight=FontWeight.Bold,maxLines=1,overflow=TextOverflow.Ellipsis);Text(if(g.status=="LIVE")"LIVE • ${g.detail}"else formatTime(g.start),color=if(g.status=="LIVE")Color(0xFFFF536C)Color(0xFF7F8795),fontSize=10.sp)};if(g.status=="LIVE")Button(onClick={streamFilter="$league ${g.away} ${g.home}"},colors=ButtonDefaults.buttonColors(containerColor=Color(0xFFFF1744))){Text("WATCH")}else Text("UPCOMING",color=Color(0xFF9BA4B2),fontSize=9.sp,fontWeight=FontWeight.Black)}}}}}
 }
}
private fun dayLabel(t:Long)=SimpleDateFormat("EEE, MMM d",Locale.US).apply{timeZone=TimeZone.getDefault()}.format(Date(t))
private fun formatTime(t:Long)=SimpleDateFormat("EEE • h:mm a",Locale.US).apply{timeZone=TimeZone.getDefault()}.format(Date(t))
