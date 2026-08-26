package com.xsportsx.app

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

private val FavRed = Color(0xFFFF1838)
private val FavBg = Color(0xFF05060A)
private val FavPanel = Color(0xFF0D121A)
private val FavPanel2 = Color(0xFF141A24)
private val FavMuted = Color(0xFF7D8797)

data class FavoriteTeam(val name:String, val league:String, val sport:String, val abbr:String)
data class FavoriteNews(val team:String, val headline:String, val description:String, val published:String, val url:String)

object FavoritesStore {
    private const val PREFS = "xsportsx_favorites"
    private const val KEY = "teams"
    fun load(context:Context):List<FavoriteTeam>{
        val raw=context.getSharedPreferences(PREFS,Context.MODE_PRIVATE).getStringSet(KEY,emptySet()).orEmpty()
        return raw.mapNotNull { decode(it) }.sortedBy { it.name }
    }
    fun save(context:Context, teams:List<FavoriteTeam>){
        context.getSharedPreferences(PREFS,Context.MODE_PRIVATE).edit().putStringSet(KEY,teams.map{encode(it)}.toSet()).apply()
    }
    private fun encode(t:FavoriteTeam) = listOf(t.league,t.sport,t.abbr,t.name).joinToString("|")
    private fun decode(v:String):FavoriteTeam?{
        val p=v.split("|",limit=4); if(p.size!=4)return null
        return FavoriteTeam(p[3],p[0],p[1],p[2])
    }
}

private val favoriteTeams = listOf(
    "NFL|Football|ARI|Arizona Cardinals","NFL|Football|ATL|Atlanta Falcons","NFL|Football|BAL|Baltimore Ravens","NFL|Football|BUF|Buffalo Bills","NFL|Football|CAR|Carolina Panthers","NFL|Football|CHI|Chicago Bears","NFL|Football|CIN|Cincinnati Bengals","NFL|Football|CLE|Cleveland Browns","NFL|Football|DAL|Dallas Cowboys","NFL|Football|DEN|Denver Broncos","NFL|Football|DET|Detroit Lions","NFL|Football|GB|Green Bay Packers","NFL|Football|HOU|Houston Texans","NFL|Football|IND|Indianapolis Colts","NFL|Football|JAX|Jacksonville Jaguars","NFL|Football|KC|Kansas City Chiefs","NFL|Football|LV|Las Vegas Raiders","NFL|Football|LAC|Los Angeles Chargers","NFL|Football|LAR|Los Angeles Rams","NFL|Football|MIA|Miami Dolphins","NFL|Football|MIN|Minnesota Vikings","NFL|Football|NE|New England Patriots","NFL|Football|NO|New Orleans Saints","NFL|Football|NYG|New York Giants","NFL|Football|NYJ|New York Jets","NFL|Football|PHI|Philadelphia Eagles","NFL|Football|PIT|Pittsburgh Steelers","NFL|Football|SF|San Francisco 49ers","NFL|Football|SEA|Seattle Seahawks","NFL|Football|TB|Tampa Bay Buccaneers","NFL|Football|TEN|Tennessee Titans","NFL|Football|WAS|Washington Commanders",
    "NBA|Basketball|ATL|Atlanta Hawks","NBA|Basketball|BOS|Boston Celtics","NBA|Basketball|BKN|Brooklyn Nets","NBA|Basketball|CHA|Charlotte Hornets","NBA|Basketball|CHI|Chicago Bulls","NBA|Basketball|CLE|Cleveland Cavaliers","NBA|Basketball|DAL|Dallas Mavericks","NBA|Basketball|DEN|Denver Nuggets","NBA|Basketball|DET|Detroit Pistons","NBA|Basketball|GS|Golden State Warriors","NBA|Basketball|HOU|Houston Rockets","NBA|Basketball|IND|Indiana Pacers","NBA|Basketball|LAC|LA Clippers","NBA|Basketball|LAL|Los Angeles Lakers","NBA|Basketball|MEM|Memphis Grizzlies","NBA|Basketball|MIA|Miami Heat","NBA|Basketball|MIL|Milwaukee Bucks","NBA|Basketball|MIN|Minnesota Timberwolves","NBA|Basketball|NO|New Orleans Pelicans","NBA|Basketball|NY|New York Knicks","NBA|Basketball|OKC|Oklahoma City Thunder","NBA|Basketball|ORL|Orlando Magic","NBA|Basketball|PHI|Philadelphia 76ers","NBA|Basketball|PHX|Phoenix Suns","NBA|Basketball|POR|Portland Trail Blazers","NBA|Basketball|SAC|Sacramento Kings","NBA|Basketball|SA|San Antonio Spurs","NBA|Basketball|TOR|Toronto Raptors","NBA|Basketball|UTA|Utah Jazz","NBA|Basketball|WAS|Washington Wizards",
    "MLB|Baseball|ARI|Arizona Diamondbacks","MLB|Baseball|ATL|Atlanta Braves","MLB|Baseball|BAL|Baltimore Orioles","MLB|Baseball|BOS|Boston Red Sox","MLB|Baseball|CHC|Chicago Cubs","MLB|Baseball|CWS|Chicago White Sox","MLB|Baseball|CIN|Cincinnati Reds","MLB|Baseball|CLE|Cleveland Guardians","MLB|Baseball|COL|Colorado Rockies","MLB|Baseball|DET|Detroit Tigers","MLB|Baseball|HOU|Houston Astros","MLB|Baseball|KC|Kansas City Royals","MLB|Baseball|LAA|Los Angeles Angels","MLB|Baseball|LAD|Los Angeles Dodgers","MLB|Baseball|MIA|Miami Marlins","MLB|Baseball|MIL|Milwaukee Brewers","MLB|Baseball|MIN|Minnesota Twins","MLB|Baseball|NYM|New York Mets","MLB|Baseball|NYY|New York Yankees","MLB|Baseball|OAK|Athletics","MLB|Baseball|PHI|Philadelphia Phillies","MLB|Baseball|PIT|Pittsburgh Pirates","MLB|Baseball|SD|San Diego Padres","MLB|Baseball|SEA|Seattle Mariners","MLB|Baseball|SF|San Francisco Giants","MLB|Baseball|STL|St. Louis Cardinals","MLB|Baseball|TB|Tampa Bay Rays","MLB|Baseball|TEX|Texas Rangers","MLB|Baseball|TOR|Toronto Blue Jays","MLB|Baseball|WSH|Washington Nationals",
    "NHL|Hockey|ANA|Anaheim Ducks","NHL|Hockey|BOS|Boston Bruins","NHL|Hockey|BUF|Buffalo Sabres","NHL|Hockey|CGY|Calgary Flames","NHL|Hockey|CAR|Carolina Hurricanes","NHL|Hockey|CHI|Chicago Blackhawks","NHL|Hockey|COL|Colorado Avalanche","NHL|Hockey|CBJ|Columbus Blue Jackets","NHL|Hockey|DAL|Dallas Stars","NHL|Hockey|DET|Detroit Red Wings","NHL|Hockey|EDM|Edmonton Oilers","NHL|Hockey|FLA|Florida Panthers","NHL|Hockey|LAK|Los Angeles Kings","NHL|Hockey|MIN|Minnesota Wild","NHL|Hockey|MTL|Montreal Canadiens","NHL|Hockey|NSH|Nashville Predators","NHL|Hockey|NJD|New Jersey Devils","NHL|Hockey|NYI|New York Islanders","NHL|Hockey|NYR|New York Rangers","NHL|Hockey|OTT|Ottawa Senators","NHL|Hockey|PHI|Philadelphia Flyers","NHL|Hockey|PIT|Pittsburgh Penguins","NHL|Hockey|SJS|San Jose Sharks","NHL|Hockey|SEA|Seattle Kraken","NHL|Hockey|STL|St. Louis Blues","NHL|Hockey|TBL|Tampa Bay Lightning","NHL|Hockey|TOR|Toronto Maple Leafs","NHL|Hockey|UTA|Utah Mammoth","NHL|Hockey|VAN|Vancouver Canucks","NHL|Hockey|VGK|Vegas Golden Knights","NHL|Hockey|WPG|Winnipeg Jets","NHL|Hockey|WSH|Washington Capitals"
).map{val p=it.split("|");FavoriteTeam(p[3],p[0],p[1],p[2])}

@Composable
fun FavoritesCenter(tvMode:Boolean=false){
    val context=androidx.compose.ui.platform.LocalContext.current
    var selected by remember { mutableStateOf(FavoritesStore.load(context)) }
    var showPicker by remember { mutableStateOf(false) }
    var refresh by remember { mutableIntStateOf(0) }
    var news by remember { mutableStateOf<List<FavoriteNews>>(emptyList()) }
    var loadingNews by remember { mutableStateOf(false) }
    var activeTeam by remember { mutableStateOf<FavoriteTeam?>(null) }
    val allEvents by produceState<List<SportsEvent>>(emptyList(),selected,refresh){ value=runCatching{SportsScheduleService.load()}.getOrDefault(emptyList()) }
    val selectedEvents=remember(allEvents,selected){allEvents.filter{event->selected.any{team->teamMatches(team,event)}}}
    LaunchedEffect(selected,refresh){
        if(selected.isEmpty()){news=emptyList();return@LaunchedEffect}
        loadingNews=true
        news=loadFavoriteNews(selected.take(6))
        loadingNews=false
    }
    Column(Modifier.fillMaxSize().background(FavBg).padding(if(tvMode) 28.dp else 18.dp)){
        Row(verticalAlignment=Alignment.CenterVertically,modifier=Modifier.fillMaxWidth()){
            Column(Modifier.weight(1f)){Text("MY TEAMS",color=Color.White,fontSize=if(tvMode)30.sp else 24.sp,fontWeight=FontWeight.Black);Text("Your teams • live • upcoming • news",color=FavMuted,fontSize=11.sp)}
            OutlinedButton(onClick={showPicker=true},shape=RoundedCornerShape(14.dp),colors=ButtonDefaults.outlinedButtonColors(contentColor=Color.White)){Text("＋ SELECT TEAMS",fontSize=10.sp,fontWeight=FontWeight.Black)}
            Spacer(Modifier.width(8.dp));TextButton(onClick={refresh++}){Text("REFRESH",color=FavRed,fontWeight=FontWeight.Black,fontSize=10.sp)}
        }
        Spacer(Modifier.height(16.dp))
        if(selected.isEmpty()){
            EmptyFavorites(onSelect={showPicker=true},tvMode=tvMode)
        }else{
            LazyRow(horizontalArrangement=Arrangement.spacedBy(9.dp),contentPadding=PaddingValues(end=8.dp)){
                items(selected){team->FavoriteTeamChip(team,activeTeam==team){activeTeam=team}}
            }
            Spacer(Modifier.height(16.dp))
            if(activeTeam!=null){
                val teamEvents=selectedEvents.filter{teamMatches(activeTeam!!,it)}
                FavoriteTeamHero(activeTeam!!,teamEvents,tvMode)
                Spacer(Modifier.height(14.dp))
            }
            FavoriteSection("LIVE NOW",if(selectedEvents.any{it.isLive})"${selectedEvents.count{it.isLive}} LIVE" else "NO LIVE GAMES")
            val live=selectedEvents.filter{it.isLive}
            if(live.isNotEmpty()) FavoriteEventRow(live,tvMode) else FavoriteEmptyRow("None of your selected teams are live right now")
            Spacer(Modifier.height(12.dp))
            FavoriteSection("UPCOMING GAMES","NEXT 30 DAYS")
            val upcoming=selectedEvents.filter{it.isUpcoming}.take(24)
            if(upcoming.isNotEmpty()) FavoriteEventRow(upcoming,tvMode) else FavoriteEmptyRow("No upcoming games found")
            Spacer(Modifier.height(12.dp))
            FavoriteSection("TEAM NEWS",if(loadingNews)"UPDATING" else "LATEST")
            if(news.isNotEmpty()) FavoriteNewsRow(news,tvMode) else FavoriteEmptyRow("No matching team news available yet")
        }
    }
    if(showPicker) TeamPickerDialog(selected){chosen->selected=chosen;FavoritesStore.save(context,chosen);showPicker=false;activeTeam=chosen.firstOrNull()}
}

private fun teamMatches(team:FavoriteTeam,event:SportsEvent):Boolean{
    val names=listOf(event.home,event.away,event.title).map{it.lowercase()}
    val target=team.name.lowercase();val abbr=team.abbr.lowercase()
    return names.any{it.contains(target)||it.contains(abbr)||target.contains(it)&&it.length>3}
}

@Composable private fun EmptyFavorites(onSelect:()->Unit,tvMode:Boolean){Column(Modifier.fillMaxWidth().padding(top=70.dp),horizontalAlignment=Alignment.CenterHorizontally){Text("★",color=FavRed,fontSize=54.sp);Spacer(Modifier.height(10.dp));Text("BUILD YOUR SPORTS FEED",color=Color.White,fontSize=20.sp,fontWeight=FontWeight.Black);Text("Pick your teams and XSportsX will put their live games, schedules and news here.",color=FavMuted,fontSize=12.sp,maxLines=2);Spacer(Modifier.height(16.dp));Button(onClick=onSelect,shape=RoundedCornerShape(13.dp)){Text("SELECT MY TEAMS",fontWeight=FontWeight.Black)}}}

@Composable private fun FavoriteTeamChip(team:FavoriteTeam,active:Boolean,onClick:()->Unit){Column(Modifier.width(150.dp).clip(RoundedCornerShape(14.dp)).background(if(active)Color(0xFF251019)else FavPanel).border(1.dp,FavRed.copy(alpha=if(active)1f else .18f),RoundedCornerShape(14.dp)).clickable{onClick()}.padding(12.dp)){Text(team.league,color=FavRed,fontSize=8.sp,fontWeight=FontWeight.Black);Text(team.abbr,color=Color.White,fontSize=15.sp,fontWeight=FontWeight.Black);Text(team.name,color=FavMuted,fontSize=9.sp,maxLines=1,overflow=TextOverflow.Ellipsis)}}

@Composable private fun FavoriteTeamHero(team:FavoriteTeam,events:List<SportsEvent>,tvMode:Boolean){Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Brushes.hero).padding(18.dp),verticalAlignment=Alignment.CenterVertically){Column(Modifier.weight(1f)){Text(team.league,color=FavRed,fontSize=9.sp,fontWeight=FontWeight.Black,letterSpacing=1.2.sp);Text(team.name,color=Color.White,fontSize=if(tvMode)25.sp else 19.sp,fontWeight=FontWeight.Black);Text(if(events.isEmpty())"No scheduled events in the current feed" else "${events.count{it.isLive}} live • ${events.count{it.isUpcoming}} upcoming",color=FavMuted,fontSize=11.sp)};Text(team.abbr,color=Color.White.copy(alpha=.15f),fontSize=48.sp,fontWeight=FontWeight.Black)}}

private object Brushes{val hero=androidx.compose.ui.graphics.Brush.horizontalGradient(listOf(Color(0xFF320913),Color(0xFF111923),Color(0xFF10131A)))}

@Composable private fun FavoriteSection(title:String,meta:String){Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.Bottom){Text(title,color=Color.White,fontSize=15.sp,fontWeight=FontWeight.Black,letterSpacing=1.1.sp);Spacer(Modifier.width(8.dp));Text(meta,color=FavMuted,fontSize=8.sp,fontWeight=FontWeight.Black)}}

@Composable private fun FavoriteEventRow(events:List<SportsEvent>,tvMode:Boolean){LazyRow(horizontalArrangement=Arrangement.spacedBy(12.dp),contentPadding=PaddingValues(top=9.dp,bottom=4.dp)){items(events){event->Column(Modifier.width(if(tvMode)300.dp else 245.dp).clip(RoundedCornerShape(16.dp)).background(FavPanel).padding(14.dp)){Row{Text(event.league,color=FavRed,fontSize=8.sp,fontWeight=FontWeight.Black);Spacer(Modifier.weight(1f));Text(if(event.isLive)"LIVE" else "UPCOMING",color=if(event.isLive)FavRed else FavMuted,fontSize=8.sp,fontWeight=FontWeight.Black)};Spacer(Modifier.height(7.dp));Text(event.title.ifBlank{"${event.away} vs ${event.home}"},color=Color.White,fontSize=12.sp,fontWeight=FontWeight.Bold,maxLines=2,overflow=TextOverflow.Ellipsis);Spacer(Modifier.height(6.dp));Text(event.status.ifBlank{"Scheduled"},color=FavMuted,fontSize=9.sp);if(event.broadcast.isNotBlank()){Text("📺 ${event.broadcast}",color=Color(0xFFB6BFCC),fontSize=9.sp,maxLines=1,overflow=TextOverflow.Ellipsis)}}}}

@Composable private fun FavoriteEmptyRow(text:String){Box(Modifier.fillMaxWidth().padding(vertical=10.dp).clip(RoundedCornerShape(14.dp)).background(FavPanel).padding(15.dp)){Text(text,color=FavMuted,fontSize=11.sp)}}

@Composable private fun FavoriteNewsRow(items:List<FavoriteNews>,tvMode:Boolean){LazyRow(horizontalArrangement=Arrangement.spacedBy(12.dp),contentPadding=PaddingValues(top=9.dp,bottom=4.dp)){items(items){n->Column(Modifier.width(if(tvMode)330.dp else 260.dp).clip(RoundedCornerShape(16.dp)).background(FavPanel).padding(14.dp)){Text(n.team,color=FavRed,fontSize=8.sp,fontWeight=FontWeight.Black);Spacer(Modifier.height(6.dp));Text(n.headline,color=Color.White,fontSize=12.sp,fontWeight=FontWeight.Bold,maxLines=3,overflow=TextOverflow.Ellipsis);Spacer(Modifier.height(6.dp));Text(n.published,color=FavMuted,fontSize=8.sp);if(n.description.isNotBlank())Text(n.description,color=Color(0xFF9AA3B1),fontSize=9.sp,maxLines=3,overflow=TextOverflow.Ellipsis)}}}}

@Composable private fun TeamPickerDialog(current:List<FavoriteTeam>,onDone:(List<FavoriteTeam>)->Unit){var selected by remember(current){mutableStateOf(current.toSet())};var query by remember{mutableStateOf("")};AlertDialog(onDismissRequest={onDone(current)},containerColor=FavPanel,title={Text("SELECT YOUR TEAMS",color=Color.White,fontWeight=FontWeight.Black)},text={Column(Modifier.fillMaxWidth()){OutlinedTextField(query,{query=it},Modifier.fillMaxWidth(),singleLine=true,label={Text("Search teams")});Spacer(Modifier.height(8.dp));LazyColumn(Modifier.heightIn(max=390.dp)){items(favoriteTeams.filter{query.isBlank()||it.name.contains(query,true)||it.league.contains(query,true)||it.abbr.contains(query,true)}){team->val checked=selected.contains(team);Row(Modifier.fillMaxWidth().clickable{selected=if(checked)selected-team else selected+team}.padding(vertical=7.dp),verticalAlignment=Alignment.CenterVertically){Checkbox(checked,{selected=if(checked)selected-team else selected+team},colors=CheckboxDefaults.colors(checkedColor=FavRed));Column{Text(team.name,color=Color.White,fontSize=12.sp,fontWeight=FontWeight.Bold);Text("${team.league} • ${team.abbr}",color=FavMuted,fontSize=9.sp)}}}}}},confirmButton={Button(onClick={onDone(selected.sortedBy{it.name})}){Text("SAVE ${selected.size}",fontWeight=FontWeight.Black)}},dismissButton={TextButton(onClick={onDone(current)}){Text("CANCEL")}})}

private suspend fun loadFavoriteNews(teams:List<FavoriteTeam>):List<FavoriteNews> = withContext(Dispatchers.IO){
    teams.flatMap{team->runCatching{fetchNews(team)}.getOrDefault(emptyList())}.sortedByDescending{it.published}.take(18)
}

private fun fetchNews(team:FavoriteTeam):List<FavoriteNews>{
    val league=when(team.league){"NFL"->"football/nfl";"NBA"->"basketball/nba";"MLB"->"baseball/mlb";"NHL"->"hockey/nhl";else->return emptyList()}
    val url="https://site.api.espn.com/apis/site/v2/sports/$league/news?limit=50"
    val c=(URL(url).openConnection() as HttpURLConnection).apply{requestMethod="GET";connectTimeout=2200;readTimeout=4500;setRequestProperty("User-Agent","XSportsX/1.7")}
    return try{
        if(c.responseCode !in 200..299)return emptyList()
        val root=JSONObject(c.inputStream.bufferedReader().use{it.readText()});val articles=root.optJSONArray("articles")?:JSONArray();val out=ArrayList<FavoriteNews>()
        val tokens=listOf(team.name.lowercase(),team.abbr.lowercase())
        for(i in 0 until articles.length()){
            val a=articles.optJSONObject(i)?:continue;val headline=a.optString("headline");val desc=a.optString("description");val text=(headline+" "+desc).lowercase()
            if(tokens.any{text.contains(it)}) out+=FavoriteNews(team.abbr,headline,desc,a.optString("published"),a.optString("links"))
        }
        out.take(6)
    }finally{c.disconnect()}
}
