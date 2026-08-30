package com.xsportsx.app

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil3.compose.AsyncImage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
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

val liveLeagues = listOf(TvLeague("NFL","football","nfl"),TvLeague("NCAA FB","football","college-football"),TvLeague("NBA","basketball","nba"),TvLeague("WNBA","basketball","wnba"),TvLeague("NCAA BB","basketball","mens-college-basketball"),TvLeague("MLB","baseball","mlb"),TvLeague("NHL","hockey","nhl"),TvLeague("MLS","soccer","usa.1"),TvLeague("EPL","soccer","eng.1"))
private val tvSports = listOf(TvSport("NFL","NFL"),TvSport("NBA","NBA"),TvSport("NCAA FB","NCAA"),TvSport("NCAA BB","NCAA"),TvSport("MLB","MLB"),TvSport("NHL","NHL"),TvSport("UFC","UFC"),TvSport("BOXING","BOX"))
private val tvNetworks = listOf(TvNetwork("ESPN","ESPN"),TvNetwork("ESPN2","ESPN2"),TvNetwork("ESPNU","ESPNU"),TvNetwork("NFL NETWORK","NFL"),TvNetwork("FS1","FS1"),TvNetwork("CBS SPORTS","CBS"),TvNetwork("SEC NETWORK","SEC"),TvNetwork("ACC NETWORK","ACC"),TvNetwork("BIG TEN NETWORK","B1G"),TvNetwork("ESPN+","ESPN+"))

private fun dateRange():String { val fmt=SimpleDateFormat("yyyyMMdd",Locale.US).apply{timeZone=TimeZone.getTimeZone("UTC")}; val cal=Calendar.getInstance(TimeZone.getTimeZone("UTC")); val today=fmt.format(cal.time); cal.add(Calendar.DAY_OF_YEAR,3); return "$today-${fmt.format(cal.time)}" }
private fun tvJson(url:String):JSONObject? { val c=try{URL(url).openConnection() as HttpURLConnection}catch(_:Exception){return null}; return try{c.connectTimeout=3000;c.readTimeout=5000;c.requestMethod="GET";c.setRequestProperty("User-Agent","XSportsX/1.7");c.setRequestProperty("Accept","application/json");if(c.responseCode !in 200..299)null else c.inputStream.bufferedReader().use{JSONObject(it.readText())}}catch(_:Exception){null}finally{c.disconnect()} }
private fun eventMillis(event:JSONObject):Long=try{java.time.Instant.parse(event.optString("date")).toEpochMilli()}catch(_:Exception){0L}

private fun parseTvGames(league: TvLeague, root: JSONObject?, liveOnly: Boolean, now: Long): List<TvGame> {
    val events = root?.optJSONArray("events") ?: return emptyList()
    return buildList {
        for(i in 0 until events.length()) {
            val event=events.optJSONObject(i)?:continue
            val competition=event.optJSONArray("competitions")?.optJSONObject(0)?:continue
            val status=competition.optJSONObject("status")?.optJSONObject("type")?:continue
            val state=status.optString("state")
            if(liveOnly && state!="in") continue
            if(!liveOnly && (state=="in" || eventMillis(event)<=now)) continue
            val competitors=competition.optJSONArray("competitors")?:continue
            var home="TBD";var away="TBD";var homeScore="0";var awayScore="0";var homeLogo="";var awayLogo=""
            for(j in 0 until competitors.length()){
                val team=competitors.optJSONObject(j)?:continue
                val teamObj=team.optJSONObject("team")?:continue
                val name=teamObj.optString("abbreviation").ifBlank{teamObj.optString("shortDisplayName")}.ifBlank{"TBD"}
                val score=team.optString("score").ifBlank{"0"}
                val logo=teamObj.optJSONArray("logos")?.optJSONObject(0)?.optString("href").orEmpty()
                if(team.optString("homeAway")=="home"){home=name;homeScore=score;homeLogo=logo}else{away=name;awayScore=score;awayLogo=logo}
            }
            val detail=status.optString("shortDetail").ifBlank{status.optString("detail")}.ifBlank{"UPCOMING"}
            val network=competition.optJSONArray("broadcasts")?.optJSONObject(0)?.optJSONArray("names")?.optString(0).orEmpty().ifBlank{"TBD"}
            add(TvGame(league.name,home,away,homeLogo,awayLogo,if(state=="pre")"—" else "$awayScore  •  $homeScore",detail,network,state=="in",eventMillis(event)))
        }
    }
}

private suspend fun loadTvGames(liveOnly:Boolean=true):List<TvGame> = withContext(Dispatchers.IO) {
    val now=System.currentTimeMillis()
    liveLeagues.map { league ->
        async {
            val url="https://site.api.espn.com/apis/site/v2/sports/${league.sport}/${league.id}/scoreboard?dates=${dateRange()}&limit=50"
            runCatching { parseTvGames(league,tvJson(url),liveOnly,now) }.getOrDefault(emptyList())
        }
    }.awaitAll().flatten().sortedBy{it.timestamp}.take(40)
}

@Composable fun TvHome(onConnect:()->Unit={},onNetwork:(String)->Unit={}){
    var selectedNav by remember{mutableStateOf("HOME")}
    var liveGames by remember{mutableStateOf<List<TvGame>>(emptyList())}
    var upcomingGames by remember{mutableStateOf<List<TvGame>>(emptyList())}
    var loadingLive by remember{mutableStateOf(true)}
    var loadingUpcoming by remember{mutableStateOf(true)}
    val scroll=rememberScrollState()

    LaunchedEffect(Unit){
        while(isActive){
            loadingLive=liveGames.isEmpty()
            if(upcomingGames.isEmpty()) loadingUpcoming=true
            val result=runCatching{
                kotlinx.coroutines.coroutineScope {
                    val live=async{loadTvGames(true)}
                    val upcoming=async{loadTvGames(false)}
                    live.await() to upcoming.await()
                }
            }.getOrNull()
            if(result!=null){
                liveGames=result.first
                upcomingGames=result.second
            }
            loadingLive=false
            loadingUpcoming=false
            delay(60_000)
        }
    }
    LaunchedEffect(selectedNav){
        if(selectedNav=="UPCOMING"&&upcomingGames.isEmpty()&&!loadingUpcoming){
            loadingUpcoming=true
            upcomingGames=runCatching{loadTvGames(false)}.getOrDefault(emptyList())
            loadingUpcoming=false
        }
    }
    Box(Modifier.fillMaxSize().background(TvBg)){
        TvBackdrop(Modifier.fillMaxSize())
        Row(Modifier.fillMaxSize()){
            TvNav(selectedNav){selectedNav=it}
            Column(Modifier.weight(1f).fillMaxHeight().verticalScroll(scroll).padding(start=22.dp,end=30.dp,top=20.dp,bottom=76.dp)){
                TvTopBar{selectedNav="SETTINGS"};Spacer(Modifier.height(14.dp))
                when(selectedNav){
                    "HOME"->{
                        TvHero{selectedNav="LIVE NOW"};Spacer(Modifier.height(18.dp))
                        TvSection("LIVE NOW",if(liveGames.isEmpty())"Waiting for live scores" else "${liveGames.size} LIVE")
                        if(liveGames.isNotEmpty())TvGameRow(liveGames,onNetwork)else TvLiveEmpty(loadingLive)
                        Spacer(Modifier.height(16.dp))
                        TvSection("NEXT GAMES",when { loadingUpcoming -> "Loading schedule…"; upcomingGames.isNotEmpty() -> "${upcomingGames.size} UPCOMING"; else -> "NO UPCOMING GAMES" })
                        if(upcomingGames.isNotEmpty())TvGameRow(upcomingGames.take(10),onNetwork)else TvLiveEmpty(loadingUpcoming)
                        Spacer(Modifier.height(16.dp));TvSection("TOP SPORTS","FAST ACCESS");TvSportRow(tvSports,onNetwork)
                        Spacer(Modifier.height(16.dp));TvSection("SPORTS NETWORKS","LIVE SOURCES");TvNetworkGrid(tvNetworks,onNetwork)
                    }
                    "LIVE NOW"->{TvSection("LIVE NOW",if(liveGames.isEmpty())"No games live right now" else "${liveGames.size} LIVE");if(liveGames.isNotEmpty())TvGameRow(liveGames,onNetwork)else TvLiveEmpty(loadingLive)}
                    "UPCOMING"->{TvSection("UPCOMING",if(loadingUpcoming)"LOADING" else "${upcomingGames.size} EVENTS");if(upcomingGames.isNotEmpty())TvGameRow(upcomingGames,onNetwork)else TvLiveEmpty(loadingUpcoming)}
                    "NETWORKS"->{TvSection("SPORTS NETWORKS","LIVE SOURCES");TvNetworkGrid(tvNetworks,onNetwork)}
                    "FAVORITES"->{FavoritesCenter(tvMode=true)}
                    "NFL","NCAA FB","NBA","WNBA","NCAA BB","MLB","NHL","MLS","EPL"->{TvSection(selectedNav,"LIVE FEED");val games=liveGames.filter{it.league==selectedNav};if(games.isNotEmpty())TvGameRow(games,onNetwork)else TvLiveEmpty(false)}
                    "UFC","BOXING"->{TvSection(selectedNav,"EVENT FEED");TvSportRow(tvSports.filter{it.name==selectedNav},onNetwork);Spacer(Modifier.height(14.dp));TvEmpty("Select ${selectedNav} to browse available events")}
                    "SETTINGS"->TvSettings{onConnect()}
                }
            }
        }
        HomeSportsTicker(Modifier.align(Alignment.BottomCenter).fillMaxWidth())
    }
}

@Composable private fun TvBackdrop(modifier:Modifier){Box(modifier.background(Brush.verticalGradient(listOf(Color(0xFF071019),TvBg,Color(0xFF020306)))))}

@Composable private fun TvNav(selected:String,onSelect:(String)->Unit){Column(Modifier.width(210.dp).fillMaxHeight().background(Brush.horizontalGradient(listOf(Color(0xFF071019),Color(0xFF04070C)))).padding(start=22.dp,top=22.dp,end=18.dp,bottom=72.dp)){Box(Modifier.fillMaxWidth(),contentAlignment=Alignment.CenterStart){XtremeLogo(size=52.dp)};Text("XSPORTSX",color=Color.White,fontSize=13.sp,fontWeight=FontWeight.Black);Spacer(Modifier.height(22.dp));listOf("⌂" to "HOME","●" to "LIVE NOW","▣" to "UPCOMING","▤" to "NETWORKS","★" to "FAVORITES","⚙" to "SETTINGS").forEach{(icon,label)->TvNavItem(icon,label,selected==label){onSelect(label)}};Spacer(Modifier.height(18.dp));Text("SPORTS",color=TvMuted,fontSize=9.sp,fontWeight=FontWeight.Black,letterSpacing=1.4.sp);Spacer(Modifier.height(6.dp));tvSports.forEach{sport->TvSportNavItem(sport,selected==sport.name){onSelect(sport.name)}};Spacer(Modifier.weight(1f));Text("TV MODE",color=Color(0xFF596371),fontSize=10.sp,fontWeight=FontWeight.Bold)}}
@Composable private fun TvNavItem(icon:String,label:String,active:Boolean,onClick:()->Unit){var focused by remember{mutableStateOf(false)};Row(Modifier.fillMaxWidth().padding(vertical=3.dp).clip(RoundedCornerShape(16.dp)).background(if(active)Color(0xFF1A0B10)else Color.Transparent).border(1.dp,TvRed.copy(alpha=if(active||focused)1f else 0f),RoundedCornerShape(16.dp)).onFocusChanged{focused=it.isFocused}.focusable().clickable{onClick()},verticalAlignment=Alignment.CenterVertically){Text(icon,Modifier.padding(start=13.dp),color=if(active||focused)TvRed else Color.White,fontSize=19.sp);Text(label,Modifier.padding(horizontal=13.dp,vertical=11.dp),color=Color.White,fontSize=12.sp,fontWeight=if(active||focused)FontWeight.Black else FontWeight.Bold)}}
@Composable private fun TvSportNavItem(sport:TvSport,active:Boolean,onClick:()->Unit){var focused by remember{mutableStateOf(false)};Row(Modifier.fillMaxWidth().padding(vertical=2.dp).clip(RoundedCornerShape(12.dp)).background(if(active||focused)TvPanel2 else Color.Transparent).border(1.dp,TvBlue.copy(alpha=if(active||focused)1f else 0f),RoundedCornerShape(12.dp)).onFocusChanged{focused=it.isFocused}.focusable().clickable{onClick()},verticalAlignment=Alignment.CenterVertically){Text(sport.glyph,Modifier.width(36.dp).padding(start=8.dp),color=if(active||focused)TvBlue else Color.White,fontSize=10.sp,fontWeight=FontWeight.Black);Text(sport.name,Modifier.padding(vertical=7.dp),color=Color.White,fontSize=10.sp,fontWeight=FontWeight.Bold)}}
@Composable private fun TvTopBar(onSettings:()->Unit){Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){Text("XSPORTSX",color=Color.White,fontSize=18.sp,fontWeight=FontWeight.Black);Spacer(Modifier.weight(1f));Text("LIVE SPORTS",color=TvMuted,fontSize=10.sp,fontWeight=FontWeight.Black);Spacer(Modifier.width(18.dp));TvActionButton("⚙  Settings",onSettings);Spacer(Modifier.width(18.dp));Text("TV MODE",color=TvMuted,fontSize=10.sp,fontWeight=FontWeight.Black)}}
@Composable private fun TvActionButton(text:String,onClick:()->Unit){var focused by remember{mutableStateOf(false)};Box(Modifier.clip(RoundedCornerShape(14.dp)).background(if(focused)Color(0xFF241018)else Color.Transparent).border(1.dp,TvRed.copy(alpha=if(focused)1f else .35f),RoundedCornerShape(14.dp)).onFocusChanged{focused=it.isFocused}.focusable().clickable{onClick()}.padding(horizontal=12.dp,vertical=9.dp)){Text(text,color=Color.White,fontSize=12.sp,fontWeight=FontWeight.Bold)}}
@Composable private fun TvHero(onClick:()->Unit){var focused by remember{mutableStateOf(false)};Box(Modifier.fillMaxWidth().height(160.dp).clip(RoundedCornerShape(18.dp)).background(Brush.horizontalGradient(listOf(Color(0xFF16090F),Color(0xFF101824),Color(0xFF08121D)))).border(1.dp,TvRed.copy(alpha=if(focused)1f else .28f),RoundedCornerShape(18.dp)).onFocusChanged{focused=it.isFocused}.focusable().clickable{onClick()}){Row(Modifier.fillMaxSize().padding(24.dp),verticalAlignment=Alignment.CenterVertically){Column(Modifier.weight(1f)){Text("WELCOME TO",color=Color.White,fontSize=12.sp,letterSpacing=1.sp);Text("XSPORTSX",color=Color.White,fontSize=34.sp,fontWeight=FontWeight.Black);Text("YOUR ULTIMATE SPORTS COMMAND CENTER",color=Color.White,fontSize=14.sp,fontWeight=FontWeight.Bold);Spacer(Modifier.height(8.dp));Text("REAL LIVE GAMES • LIVE SCORES • NETWORKS",color=TvMuted,fontSize=10.sp,fontWeight=FontWeight.Bold)};Column(Modifier.width(220.dp).clip(RoundedCornerShape(16.dp)).background(Color(0xAA0A111A)).padding(16.dp)){Text("LIVE SPORTS",color=TvRed,fontSize=13.sp,fontWeight=FontWeight.Black);Text("Fast score refresh",color=Color.White,fontSize=15.sp,fontWeight=FontWeight.Bold);Text("Your teams and games in one place",color=TvMuted,fontSize=10.sp)}}}}
@Composable private fun TvSection(title:String,subtitle:String=""){Row(Modifier.fillMaxWidth().padding(bottom=8.dp),verticalAlignment=Alignment.Bottom){Text(title,color=Color.White,fontSize=19.sp,fontWeight=FontWeight.Black);if(subtitle.isNotBlank()){Spacer(Modifier.width(10.dp));Text(subtitle,color=TvMuted,fontSize=10.sp,fontWeight=FontWeight.Bold)}}}
@Composable private fun TvGameRow(games:List<TvGame>,onNetwork:(String)->Unit){LazyRow(horizontalArrangement=Arrangement.spacedBy(12.dp),contentPadding=PaddingValues(bottom=4.dp)){items(games,key={"${it.league}-${it.timestamp}-${it.home}-${it.away}"}){game->TvGameCard(game,onNetwork)}}}
@Composable private fun TvGameCard(game:TvGame,onNetwork:(String)->Unit){var focused by remember{mutableStateOf(false)};Column(Modifier.width(270.dp).clip(RoundedCornerShape(16.dp)).background(TvPanel).border(1.dp,if(focused)TvRed else TvRed.copy(alpha=.22f),RoundedCornerShape(16.dp)).onFocusChanged{focused=it.isFocused}.focusable().clickable{onNetwork(game.network)}.padding(14.dp)){Row(verticalAlignment=Alignment.CenterVertically){Text(game.league,color=TvBlue,fontSize=10.sp,fontWeight=FontWeight.Black);Spacer(Modifier.weight(1f));Text(if(game.live)"● LIVE" else "UPCOMING",color=if(game.live)TvRed else TvMuted,fontSize=9.sp,fontWeight=FontWeight.Black)};Spacer(Modifier.height(10.dp));TvTeamRow(game.away,game.awayLogo,game.score.substringBefore("  •"));Spacer(Modifier.height(6.dp));TvTeamRow(game.home,game.homeLogo,game.score.substringAfter("•  ","—"));Spacer(Modifier.height(10.dp));Text(game.status,color=Color.White,fontSize=10.sp,fontWeight=FontWeight.Bold,maxLines=1,overflow=TextOverflow.Ellipsis);Text(game.network,color=TvMuted,fontSize=9.sp)}}
@Composable private fun TvTeamRow(name:String,logo:String,score:String){Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){if(logo.isNotBlank())AsyncImage(model=logo,contentDescription=name,modifier=Modifier.size(28.dp),contentScale=ContentScale.Fit)else Box(Modifier.size(28.dp).clip(RoundedCornerShape(8.dp)).background(TvPanel2),contentAlignment=Alignment.Center){Text(name.take(2),color=Color.White,fontSize=8.sp,fontWeight=FontWeight.Black)};Spacer(Modifier.width(9.dp));Text(name,Modifier.weight(1f),color=Color.White,fontSize=13.sp,fontWeight=FontWeight.Bold,maxLines=1,overflow=TextOverflow.Ellipsis);Text(score,color=Color.White,fontSize=17.sp,fontWeight=FontWeight.Black)}}
@Composable private fun TvSportRow(sports:List<TvSport>,onNetwork:(String)->Unit){LazyRow(horizontalArrangement=Arrangement.spacedBy(10.dp),contentPadding=PaddingValues(bottom=4.dp)){items(sports,key={it.name}){TvTile(it.name,it.glyph,TvBlue){onNetwork(it.name)}}}}
@Composable private fun TvNetworkGrid(networks:List<TvNetwork>,onNetwork:(String)->Unit){Column(verticalArrangement=Arrangement.spacedBy(8.dp)){networks.chunked(5).forEach{row->Row(horizontalArrangement=Arrangement.spacedBy(8.dp),modifier=Modifier.fillMaxWidth()){row.forEach{network->TvTile(network.name,network.mark,TvRed){onNetwork(network.name)}}}}}}
@Composable private fun TvTile(title:String,mark:String,accent:Color,onClick:()->Unit){var focused by remember{mutableStateOf(false)};Column(Modifier.width(120.dp).height(70.dp).clip(RoundedCornerShape(14.dp)).background(TvPanel).border(1.dp,accent.copy(alpha=if(focused)1f else .25f),RoundedCornerShape(14.dp)).onFocusChanged{focused=it.isFocused}.focusable().clickable{onClick()}.padding(10.dp),verticalArrangement=Arrangement.Center){Text(mark,color=accent,fontSize=15.sp,fontWeight=FontWeight.Black);Text(title,color=Color.White,fontSize=9.sp,fontWeight=FontWeight.Bold,maxLines=1,overflow=TextOverflow.Ellipsis)}}
@Composable fun TvEmpty(message:String){Box(Modifier.fillMaxWidth().height(170.dp).clip(RoundedCornerShape(16.dp)).background(TvPanel).border(1.dp,TvBlue.copy(alpha=.2f),RoundedCornerShape(16.dp)),contentAlignment=Alignment.Center){Text(message,color=TvMuted,fontSize=12.sp,fontWeight=FontWeight.Bold)}}
@Composable private fun TvLiveEmpty(loading:Boolean){Box(Modifier.fillMaxWidth().height(170.dp).clip(RoundedCornerShape(16.dp)).background(TvPanel).border(1.dp,TvRed.copy(alpha=.18f),RoundedCornerShape(16.dp)),contentAlignment=Alignment.Center){Column(horizontalAlignment=Alignment.CenterHorizontally){Text(if(loading)"LOADING LIVE GAMES…" else "NO LIVE GAMES RIGHT NOW",color=Color.White,fontSize=15.sp,fontWeight=FontWeight.Black);Text("Live scores refresh automatically",color=TvMuted,fontSize=10.sp)}}}
@Composable private fun TvSettings(onConnect:()->Unit){TvSection("SETTINGS","PAIRING");Column(verticalArrangement=Arrangement.spacedBy(10.dp)){PairingQrCard(Modifier.fillMaxWidth());TvActionButton("OPEN CONNECTION SETTINGS",onConnect)}}
