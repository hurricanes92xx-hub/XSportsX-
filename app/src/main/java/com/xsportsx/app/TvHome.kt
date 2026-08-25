package com.xsportsx.app

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil3.compose.AsyncImage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale
import java.util.TimeZone

private val TvRed = Color(0xFFFF1838)
private val TvBlue = Color(0xFF2E8BFF)
private val TvBg = Color(0xFF03060B)
private val TvPanel = Color(0xFF0B111A)
private val TvPanel2 = Color(0xFF111923)
private val TvMuted = Color(0xFF8993A2)

private data class TvGame(val league:String,val home:String,val away:String,val homeLogo:String,val awayLogo:String,val score:String,val status:String,val network:String,val live:Boolean,val timestamp:Long)
private data class TvSport(val name:String,val glyph:String)
private data class TvNetwork(val name:String,val mark:String)
data class TvLeague(val name:String,val sport:String,val id:String)

val liveLeagues=listOf(TvLeague("NFL","football","nfl"),TvLeague("NCAA FB","football","college-football"),TvLeague("NBA","basketball","nba"),TvLeague("WNBA","basketball","wnba"),TvLeague("NCAA BB","basketball","mens-college-basketball"),TvLeague("MLB","baseball","mlb"),TvLeague("NHL","hockey","nhl"),TvLeague("MLS","soccer","usa.1"),TvLeague("EPL","soccer","eng.1"))
private val tvSports=listOf(TvSport("NFL","NFL"),TvSport("NBA","NBA"),TvSport("NCAA FB","NCAA"),TvSport("NCAA BB","NCAA"),TvSport("MLB","MLB"),TvSport("NHL","NHL"),TvSport("UFC","UFC"),TvSport("BOXING","BOX"))
private val tvNetworks=listOf(TvNetwork("ESPN","ESPN"),TvNetwork("ESPN2","ESPN2"),TvNetwork("ESPNU","ESPNU"),TvNetwork("NFL NETWORK","NFL"),TvNetwork("FS1","FS1"),TvNetwork("CBS SPORTS","CBS"),TvNetwork("SEC NETWORK","SEC"),TvNetwork("ACC NETWORK","ACC"),TvNetwork("BIG TEN NETWORK","B1G"),TvNetwork("ESPN+","ESPN+"))
private fun dateRange():String{val fmt=SimpleDateFormat("yyyyMMdd",Locale.US).apply{timeZone=TimeZone.getTimeZone("UTC")};val cal=Calendar.getInstance(TimeZone.getTimeZone("UTC"));cal.add(Calendar.DAY_OF_YEAR,-1);val yesterday=fmt.format(cal.time);cal.add(Calendar.DAY_OF_YEAR,2);return "$yesterday-${fmt.format(cal.time)}"}
private fun tvJson(url:String):JSONObject?{val c=try{URL(url).openConnection() as HttpURLConnection}catch(_:Exception){return null};return try{c.connectTimeout=3000;c.readTimeout=5000;c.requestMethod="GET";c.setRequestProperty("User-Agent","XSportsX/1.6");c.setRequestProperty("Accept","application/json");if(c.responseCode !in 200..299)null else c.inputStream.bufferedReader().use{JSONObject(it.readText())}}catch(_:Exception){null}finally{c.disconnect()}}
private fun eventMillis(event:JSONObject):Long=try{java.time.Instant.parse(event.optString("date")).toEpochMilli()}catch(_:Exception){0L}
private suspend fun loadTvGames(liveOnly:Boolean=true):List<TvGame>=withContext(Dispatchers.IO){liveLeagues.flatMap{league->val url="https://site.api.espn.com/apis/site/v2/sports/${league.sport}/${league.id}/scoreboard?dates=${dateRange()}&limit=50";val events=tvJson(url)?.optJSONArray("events")?:return@flatMap emptyList();buildList{for(i in 0 until events.length()){val event=events.optJSONObject(i)?:continue;val competition=event.optJSONArray("competitions")?.optJSONObject(0)?:continue;val status=competition.optJSONObject("status")?.optJSONObject("type")?:continue;val state=status.optString("state");if(liveOnly&&state!="in")continue;if(!liveOnly&&eventMillis(event)<=System.currentTimeMillis())continue;val competitors=competition.optJSONArray("competitors")?:continue;var home="TBD";var away="TBD";var homeScore="0";var awayScore="0";var homeLogo="";var awayLogo="";for(j in 0 until competitors.length()){val team=competitors.optJSONObject(j)?:continue;val teamObj=team.optJSONObject("team")?:continue;val name=teamObj.optString("abbreviation").ifBlank{teamObj.optString("shortDisplayName")}.ifBlank{"TBD"};val score=team.optString("score").ifBlank{"0"};val logo=teamObj.optJSONArray("logos")?.optJSONObject(0)?.optString("href").orEmpty();if(team.optString("homeAway")=="home"){home=name;homeScore=score;homeLogo=logo}else{away=name;awayScore=score;awayLogo=logo}};val detail=status.optString("shortDetail").ifBlank{status.optString("detail")}.ifBlank{if(state=="pre")"UPCOMING" else "LIVE"};val network=competition.optJSONArray("broadcasts")?.optJSONObject(0)?.optJSONArray("names")?.optString(0).orEmpty().ifBlank{"TBD"};add(TvGame(league.name,home,away,homeLogo,awayLogo,if(state=="pre")"—" else "$awayScore  •  $homeScore",detail,network,state=="in",eventMillis(event)))}}}.sortedBy{it.timestamp}.take(30)}

@Composable fun TvHome(onConnect:()->Unit={},onNetwork:(String)->Unit={}){
 var selectedNav by remember{mutableStateOf("HOME")};var liveGames by remember{mutableStateOf<List<TvGame>>(emptyList())};var upcomingGames by remember{mutableStateOf<List<TvGame>>(emptyList())};var loadingLive by remember{mutableStateOf(true)};var loadingUpcoming by remember{mutableStateOf(false)};val scroll=rememberScrollState()
 LaunchedEffect(Unit){while(isActive){loadingLive=liveGames.isEmpty();val result=runCatching{loadTvGames(true)}.getOrDefault(emptyList());if(result.isNotEmpty())liveGames=result;loadingLive=false;delay(60_000)}}
 LaunchedEffect(selectedNav){if(selectedNav=="UPCOMING"&&upcomingGames.isEmpty()){loadingUpcoming=true;upcomingGames=runCatching{loadTvGames(false)}.getOrDefault(emptyList());loadingUpcoming=false}}
 Box(Modifier.fillMaxSize().background(TvBg)){TvGlowingCracks(Modifier.fillMaxSize());Row(Modifier.fillMaxSize()){TvNav(selectedNav){selectedNav=it};Column(Modifier.weight(1f).fillMaxHeight().verticalScroll(scroll).padding(start=22.dp,end=30.dp,top=20.dp,bottom=76.dp)){TvTopBar(onConnect);Spacer(Modifier.height(14.dp));when(selectedNav){"HOME"->{TvHero(onConnect);Spacer(Modifier.height(18.dp));TvSection("LIVE NOW",if(liveGames.isEmpty())"Waiting for live scores" else "${liveGames.size} LIVE");if(liveGames.isNotEmpty())TvGameRow(liveGames,onNetwork)else TvLiveEmpty(loadingLive);Spacer(Modifier.height(16.dp));TvSection("TOP SPORTS");TvSportRow(tvSports){sport->onNetwork(sport.name)};Spacer(Modifier.height(16.dp));TvNetworksBlock(onNetwork)};"LIVE NOW"->{TvSection("LIVE NOW",if(liveGames.isEmpty())"No games live right now" else "${liveGames.size} LIVE");if(liveGames.isNotEmpty())TvGameRow(liveGames,onNetwork)else TvLiveEmpty(loadingLive)};"UPCOMING"->{TvSection("UPCOMING",if(loadingUpcoming)"LOADING" else "${upcomingGames.size} EVENTS");if(upcomingGames.isNotEmpty())TvGameRow(upcomingGames,onNetwork)else TvLiveEmpty(loadingUpcoming)};"NETWORKS"->{TvSection("SPORTS NETWORKS");TvNetworkGrid(tvNetworks,onNetwork)};"FAVORITES"->{TvSection("FAVORITES");TvEmpty("Your favorite leagues and networks will appear here")};"NFL","NCAA FB","NBA","WNBA","NCAA BB","MLB","NHL","MLS","EPL"->{TvSection(selectedNav,"LIVE FEED");val games=liveGames.filter{it.league==selectedNav};if(games.isNotEmpty())TvGameRow(games,onNetwork)else TvLiveEmpty(false)};"UFC","BOXING"->{TvSection(selectedNav,"EVENT FEED");TvSportRow(tvSports.filter{it.name==selectedNav}){sport->onNetwork(sport.name)};Spacer(Modifier.height(14.dp));TvEmpty("Select ${selectedNav} to browse available events")};"SETTINGS"->TvSettings(onConnect)}}}};HomeSportsTicker(Modifier.align(Alignment.BottomCenter).fillMaxWidth())}}
