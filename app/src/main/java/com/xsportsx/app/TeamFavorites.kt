package com.xsportsx.app

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

data class FavoriteTeam(val name:String,val league:String,val sport:String,val abbr:String)
data class FavoriteNews(val team:String,val headline:String,val description:String,val published:String,val url:String)

private val FavRed=Color(0xFFFF1838)
private val FavBg=Color(0xFF05060A)
private val FavPanel=Color(0xFF0D121A)
private val FavMuted=Color(0xFF7D8797)

object FavoritesStore{
    private const val PREFS="xsportsx_favorites"
    private const val KEY="teams"
    fun load(context:Context):List<FavoriteTeam>{
        val raw=context.getSharedPreferences(PREFS,Context.MODE_PRIVATE).getStringSet(KEY,emptySet()).orEmpty()
        return raw.mapNotNull{decode(it)}.sortedBy{it.name}
    }
    fun save(context:Context,teams:List<FavoriteTeam>){context.getSharedPreferences(PREFS,Context.MODE_PRIVATE).edit().putStringSet(KEY,teams.map{encode(it)}.toSet()).apply()}
    private fun encode(t:FavoriteTeam)=listOf(t.league,t.sport,t.abbr,t.name).joinToString("|")
    private fun decode(v:String):FavoriteTeam?{val p=v.split("|",limit=4);return if(p.size==4)FavoriteTeam(p[3],p[0],p[1],p[2])else null}
}

private fun makeTeams(league:String,sport:String,names:String):List<FavoriteTeam>=names.split(",").map{it.trim()}.filter{it.isNotBlank()}.map{n->FavoriteTeam(n,league,sport,abbrFor(n))}
private fun abbrFor(name:String)=when(name){
    "Arizona Cardinals"->"ARI";"Atlanta Falcons"->"ATL";"Baltimore Ravens"->"BAL";"Buffalo Bills"->"BUF";"Carolina Panthers"->"CAR";"Chicago Bears"->"CHI";"Cincinnati Bengals"->"CIN";"Cleveland Browns"->"CLE";"Dallas Cowboys"->"DAL";"Denver Broncos"->"DEN";"Detroit Lions"->"DET";"Green Bay Packers"->"GB";"Houston Texans"->"HOU";"Indianapolis Colts"->"IND";"Jacksonville Jaguars"->"JAX";"Kansas City Chiefs"->"KC";"Las Vegas Raiders"->"LV";"Los Angeles Chargers"->"LAC";"Los Angeles Rams"->"LAR";"Miami Dolphins"->"MIA";"Minnesota Vikings"->"MIN";"New England Patriots"->"NE";"New Orleans Saints"->"NO";"New York Giants"->"NYG";"New York Jets"->"NYJ";"Philadelphia Eagles"->"PHI";"Pittsburgh Steelers"->"PIT";"San Francisco 49ers"->"SF";"Seattle Seahawks"->"SEA";"Tampa Bay Buccaneers"->"TB";"Tennessee Titans"->"TEN";"Washington Commanders"->"WAS";
    "Atlanta Hawks"->"ATL";"Boston Celtics"->"BOS";"Brooklyn Nets"->"BKN";"Charlotte Hornets"->"CHA";"Chicago Bulls"->"CHI";"Cleveland Cavaliers"->"CLE";"Dallas Mavericks"->"DAL";"Denver Nuggets"->"DEN";"Detroit Pistons"->"DET";"Golden State Warriors"->"GS";"Houston Rockets"->"HOU";"Indiana Pacers"->"IND";"LA Clippers"->"LAC";"Los Angeles Lakers"->"LAL";"Memphis Grizzlies"->"MEM";"Miami Heat"->"MIA";"Milwaukee Bucks"->"MIL";"Minnesota Timberwolves"->"MIN";"New Orleans Pelicans"->"NO";"New York Knicks"->"NY";"Oklahoma City Thunder"->"OKC";"Orlando Magic"->"ORL";"Philadelphia 76ers"->"PHI";"Phoenix Suns"->"PHX";"Portland Trail Blazers"->"POR";"Sacramento Kings"->"SAC";"San Antonio Spurs"->"SA";"Toronto Raptors"->"TOR";"Utah Jazz"->"UTA";"Washington Wizards"->"WAS";
    "Arizona Diamondbacks"->"ARI";"Atlanta Braves"->"ATL";"Baltimore Orioles"->"BAL";"Boston Red Sox"->"BOS";"Chicago Cubs"->"CHC";"Chicago White Sox"->"CWS";"Cincinnati Reds"->"CIN";"Cleveland Guardians"->"CLE";"Colorado Rockies"->"COL";"Detroit Tigers"->"DET";"Houston Astros"->"HOU";"Kansas City Royals"->"KC";"Los Angeles Angels"->"LAA";"Los Angeles Dodgers"->"LAD";"Miami Marlins"->"MIA";"Milwaukee Brewers"->"MIL";"Minnesota Twins"->"MIN";"New York Mets"->"NYM";"New York Yankees"->"NYY";"Athletics"->"ATH";"Philadelphia Phillies"->"PHI";"Pittsburgh Pirates"->"PIT";"San Diego Padres"->"SD";"Seattle Mariners"->"SEA";"San Francisco Giants"->"SF";"St. Louis Cardinals"->"STL";"Tampa Bay Rays"->"TB";"Texas Rangers"->"TEX";"Toronto Blue Jays"->"TOR";"Washington Nationals"->"WSH";
    "Anaheim Ducks"->"ANA";"Boston Bruins"->"BOS";"Buffalo Sabres"->"BUF";"Calgary Flames"->"CGY";"Carolina Hurricanes"->"CAR";"Chicago Blackhawks"->"CHI";"Colorado Avalanche"->"COL";"Columbus Blue Jackets"->"CBJ";"Dallas Stars"->"DAL";"Detroit Red Wings"->"DET";"Edmonton Oilers"->"EDM";"Florida Panthers"->"FLA";"Los Angeles Kings"->"LAK";"Minnesota Wild"->"MIN";"Montreal Canadiens"->"MTL";"Nashville Predators"->"NSH";"New Jersey Devils"->"NJD";"New York Islanders"->"NYI";"New York Rangers"->"NYR";"Ottawa Senators"->"OTT";"Philadelphia Flyers"->"PHI";"Pittsburgh Penguins"->"PIT";"San Jose Sharks"->"SJS";"Seattle Kraken"->"SEA";"St. Louis Blues"->"STL";"Tampa Bay Lightning"->"TBL";"Toronto Maple Leafs"->"TOR";"Utah Mammoth"->"UTA";"Vancouver Canucks"->"VAN";"Vegas Golden Knights"->"VGK";"Winnipeg Jets"->"WPG";"Washington Capitals"->"WSH";
    else->name.split(" ").mapNotNull{it.firstOrNull()}.joinToString("").take(3).uppercase()
}

private val favoriteTeams=buildList{
    addAll(makeTeams("NFL","Football","Arizona Cardinals,Atlanta Falcons,Baltimore Ravens,Buffalo Bills,Carolina Panthers,Chicago Bears,Cincinnati Bengals,Cleveland Browns,Dallas Cowboys,Denver Broncos,Detroit Lions,Green Bay Packers,Houston Texans,Indianapolis Colts,Jacksonville Jaguars,Kansas City Chiefs,Las Vegas Raiders,Los Angeles Chargers,Los Angeles Rams,Miami Dolphins,Minnesota Vikings,New England Patriots,New Orleans Saints,New York Giants,New York Jets,Philadelphia Eagles,Pittsburgh Steelers,San Francisco 49ers,Seattle Seahawks,Tampa Bay Buccaneers,Tennessee Titans,Washington Commanders"))
    addAll(makeTeams("NBA","Basketball","Atlanta Hawks,Boston Celtics,Brooklyn Nets,Charlotte Hornets,Chicago Bulls,Cleveland Cavaliers,Dallas Mavericks,Denver Nuggets,Detroit Pistons,Golden State Warriors,Houston Rockets,Indiana Pacers,LA Clippers,Los Angeles Lakers,Memphis Grizzlies,Miami Heat,Milwaukee Bucks,Minnesota Timberwolves,New Orleans Pelicans,New York Knicks,Oklahoma City Thunder,Orlando Magic,Philadelphia 76ers,Phoenix Suns,Portland Trail Blazers,Sacramento Kings,San Antonio Spurs,Toronto Raptors,Utah Jazz,Washington Wizards"))
    addAll(makeTeams("MLB","Baseball","Arizona Diamondbacks,Atlanta Braves,Baltimore Orioles,Boston Red Sox,Chicago Cubs,Chicago White Sox,Cincinnati Reds,Cleveland Guardians,Colorado Rockies,Detroit Tigers,Houston Astros,Kansas City Royals,Los Angeles Angels,Los Angeles Dodgers,Miami Marlins,Milwaukee Brewers,Minnesota Twins,New York Mets,New York Yankees,Athletics,Philadelphia Phillies,Pittsburgh Pirates,San Diego Padres,Seattle Mariners,San Francisco Giants,St. Louis Cardinals,Tampa Bay Rays,Texas Rangers,Toronto Blue Jays,Washington Nationals"))
    addAll(makeTeams("NHL","Hockey","Anaheim Ducks,Boston Bruins,Buffalo Sabres,Calgary Flames,Carolina Hurricanes,Chicago Blackhawks,Colorado Avalanche,Columbus Blue Jackets,Dallas Stars,Detroit Red Wings,Edmonton Oilers,Florida Panthers,Los Angeles Kings,Minnesota Wild,Montreal Canadiens,Nashville Predators,New Jersey Devils,New York Islanders,New York Rangers,Ottawa Senators,Philadelphia Flyers,Pittsburgh Penguins,San Jose Sharks,Seattle Kraken,St. Louis Blues,Tampa Bay Lightning,Toronto Maple Leafs,Utah Mammoth,Vancouver Canucks,Vegas Golden Knights,Winnipeg Jets,Washington Capitals"))
}

@Composable
fun FavoritesCenter(tvMode:Boolean=false){
    val context=LocalContext.current
    var selected by remember{mutableStateOf(FavoritesStore.load(context))}
    var picker by remember{mutableStateOf(false)}
    var active by remember{mutableStateOf<FavoriteTeam?>(selected.firstOrNull())}
    var events by remember{mutableStateOf<List<SportsEvent>>(emptyList())}
    var news by remember{mutableStateOf<List<FavoriteNews>>(emptyList())}
    var loading by remember{mutableStateOf(false)}
    LaunchedEffect(selected){
        loading=true
        events=runCatching{SportsScheduleService.load()}.getOrDefault(emptyList())
        news=loadFavoriteNews(selected.take(6))
        loading=false
        if(active==null||active !in selected)active=selected.firstOrNull()
    }
    val matching=remember(events,selected){events.filter{e->selected.any{t->teamMatches(t,e)}}}
    Column(Modifier.fillMaxSize().background(FavBg).padding(if(tvMode)28.dp else 18.dp)){
        Row(verticalAlignment=Alignment.CenterVertically,modifier=Modifier.fillMaxWidth()){
            Column(Modifier.weight(1f)){Text("MY TEAMS",color=Color.White,fontSize=if(tvMode)30.sp else 24.sp,fontWeight=FontWeight.Black);Text("Live games • schedules • team news",color=FavMuted,fontSize=11.sp)}
            OutlinedButton(onClick={picker=true},shape=RoundedCornerShape(14.dp),colors=ButtonDefaults.outlinedButtonColors(contentColor=Color.White)){Text("＋ SELECT TEAMS",fontSize=10.sp,fontWeight=FontWeight.Black)}
            Spacer(Modifier.width(8.dp));TextButton(onClick={events=emptyList();news=emptyList();}){Text("RESET",color=FavRed,fontSize=10.sp,fontWeight=FontWeight.Black)}
        }
        Spacer(Modifier.height(16.dp))
        if(selected.isEmpty()) EmptyFavorites{picker=true} else {
            LazyRow(horizontalArrangement=Arrangement.spacedBy(9.dp)){items(selected){t->TeamChip(t,t==active){active=t}}}
            Spacer(Modifier.height(14.dp))
            active?.let{t->TeamHero(t,matching.filter{e->teamMatches(t,e)},tvMode);Spacer(Modifier.height(14.dp))}
            Section("LIVE NOW",if(matching.any{it.isLive})"${matching.count{it.isLive}} LIVE" else "NO LIVE GAMES")
            val live=matching.filter{it.isLive}
            if(live.isEmpty())EmptyRow("None of your selected teams are live right now")else EventRow(live,tvMode)
            Spacer(Modifier.height(12.dp))
            Section("UPCOMING GAMES","NEXT 30 DAYS")
            val upcoming=matching.filter{it.isUpcoming}.take(24)
            if(upcoming.isEmpty())EmptyRow(if(loading)"Loading schedules…" else "No upcoming games found")else EventRow(upcoming,tvMode)
            Spacer(Modifier.height(12.dp))
            Section("TEAM NEWS",if(loading)"UPDATING" else "LATEST")
            if(news.isEmpty())EmptyRow("No matching team news available yet")else NewsRow(news,tvMode)
        }
    }
    if(picker)TeamPickerDialog(selected){chosen->selected=chosen;FavoritesStore.save(context,chosen);active=chosen.firstOrNull();picker=false}
}

private fun teamMatches(team:FavoriteTeam,event:SportsEvent):Boolean{
    val text="${event.home} ${event.away} ${event.title}".lowercase()
    val name=team.name.lowercase();val abbr=team.abbr.lowercase()
    return text.contains(name)||text.contains(abbr)||name.split(" ").filter{it.length>5}.any{text.contains(it)}
}

@Composable private fun EmptyFavorites(onSelect:()->Unit){Column(Modifier.fillMaxWidth().padding(top=70.dp),horizontalAlignment=Alignment.CenterHorizontally){Text("★",color=FavRed,fontSize=54.sp);Text("BUILD YOUR SPORTS FEED",color=Color.White,fontSize=20.sp,fontWeight=FontWeight.Black);Spacer(Modifier.height(8.dp));Text("Pick your teams for live games, schedules and news.",color=FavMuted,fontSize=12.sp);Spacer(Modifier.height(16.dp));Button(onClick=onSelect){Text("SELECT MY TEAMS",fontWeight=FontWeight.Black)}}}
@Composable private fun TeamChip(t:FavoriteTeam,active:Boolean,onClick:()->Unit){Column(Modifier.width(150.dp).clip(RoundedCornerShape(14.dp)).background(if(active)Color(0xFF251019)else FavPanel).border(1.dp,FavRed.copy(alpha=if(active)1f else .18f),RoundedCornerShape(14.dp)).clickable{onClick()}.padding(12.dp)){Text(t.league,color=FavRed,fontSize=8.sp,fontWeight=FontWeight.Black);Text(t.abbr,color=Color.White,fontSize=15.sp,fontWeight=FontWeight.Black);Text(t.name,color=FavMuted,fontSize=9.sp,maxLines=1,overflow=TextOverflow.Ellipsis)}}
@Composable private fun TeamHero(t:FavoriteTeam,games:List<SportsEvent>,tv:Boolean){Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Brush.horizontalGradient(listOf(Color(0xFF320913),Color(0xFF111923),Color(0xFF10131A)))).padding(18.dp),verticalAlignment=Alignment.CenterVertically){Column(Modifier.weight(1f)){Text(t.league,color=FavRed,fontSize=9.sp,fontWeight=FontWeight.Black);Text(t.name,color=Color.White,fontSize=if(tv)25.sp else 19.sp,fontWeight=FontWeight.Black);Text("${games.count{it.isLive}} live • ${games.count{it.isUpcoming}} upcoming",color=FavMuted,fontSize=11.sp)};Text(t.abbr,color=Color.White.copy(alpha=.15f),fontSize=48.sp,fontWeight=FontWeight.Black)}}
@Composable private fun Section(title:String,meta:String){Row(verticalAlignment=Alignment.Bottom){Text(title,color=Color.White,fontSize=15.sp,fontWeight=FontWeight.Black,letterSpacing=1.1.sp);Spacer(Modifier.width(8.dp));Text(meta,color=FavMuted,fontSize=8.sp,fontWeight=FontWeight.Black)}}
@Composable private fun EventRow(games:List<SportsEvent>,tv:Boolean){LazyRow(horizontalArrangement=Arrangement.spacedBy(12.dp),contentPadding=PaddingValues(top=8.dp,bottom=4.dp)){items(games){g->Column(Modifier.width(if(tv)300.dp else 245.dp).clip(RoundedCornerShape(16.dp)).background(FavPanel).padding(14.dp)){Row{Text(g.league,color=FavRed,fontSize=8.sp,fontWeight=FontWeight.Black);Spacer(Modifier.weight(1f));Text(if(g.isLive)"LIVE" else "UPCOMING",color=if(g.isLive)FavRed else FavMuted,fontSize=8.sp,fontWeight=FontWeight.Black)};Spacer(Modifier.height(7.dp));Text(g.title.ifBlank{"${g.away} vs ${g.home}"},color=Color.White,fontSize=12.sp,fontWeight=FontWeight.Bold,maxLines=2,overflow=TextOverflow.Ellipsis);Text(g.status.ifBlank{"Scheduled"},color=FavMuted,fontSize=9.sp);if(g.broadcast.isNotBlank())Text("📺 ${g.broadcast}",color=Color(0xFFB6BFCC),fontSize=9.sp,maxLines=1,overflow=TextOverflow.Ellipsis)}}}}
@Composable private fun EmptyRow(text:String){Box(Modifier.fillMaxWidth().padding(vertical=8.dp).clip(RoundedCornerShape(14.dp)).background(FavPanel).padding(15.dp)){Text(text,color=FavMuted,fontSize=11.sp)}}
@Composable private fun NewsRow(itemsList:List<FavoriteNews>,tv:Boolean){LazyRow(horizontalArrangement=Arrangement.spacedBy(12.dp),contentPadding=PaddingValues(top=8.dp)){items(itemsList){n->Column(Modifier.width(if(tv)330.dp else 260.dp).clip(RoundedCornerShape(16.dp)).background(FavPanel).padding(14.dp)){Text(n.team,color=FavRed,fontSize=8.sp,fontWeight=FontWeight.Black);Spacer(Modifier.height(6.dp));Text(n.headline,color=Color.White,fontSize=12.sp,fontWeight=FontWeight.Bold,maxLines=3,overflow=TextOverflow.Ellipsis);Spacer(Modifier.height(5.dp));Text(n.published,color=FavMuted,fontSize=8.sp);if(n.description.isNotBlank())Text(n.description,color=Color(0xFF9AA3B1),fontSize=9.sp,maxLines=3,overflow=TextOverflow.Ellipsis)}}}}
@Composable private fun TeamPickerDialog(current:List<FavoriteTeam>,onDone:(List<FavoriteTeam>)->Unit){var chosen by remember(current){mutableStateOf(current.toSet())};var query by remember{mutableStateOf("")};AlertDialog(onDismissRequest={onDone(current)},containerColor=FavPanel,title={Text("SELECT YOUR TEAMS",color=Color.White,fontWeight=FontWeight.Black)},text={Column(Modifier.fillMaxWidth()){OutlinedTextField(value=query,onValueChange={query=it},modifier=Modifier.fillMaxWidth(),singleLine=true,label={Text("Search teams")});Spacer(Modifier.height(8.dp));LazyColumn(Modifier.heightIn(max=390.dp)){items(favoriteTeams.filter{query.isBlank()||it.name.contains(query,true)||it.league.contains(query,true)||it.abbr.contains(query,true)}){team->val checked=team in chosen;Row(Modifier.fillMaxWidth().clickable{chosen=if(checked)chosen-team else chosen+team}.padding(vertical=6.dp),verticalAlignment=Alignment.CenterVertically){Checkbox(checked=checked,onCheckedChange={chosen=if(checked)chosen-team else chosen+team},colors=CheckboxDefaults.colors(checkedColor=FavRed));Column{Text(team.name,color=Color.White,fontSize=12.sp,fontWeight=FontWeight.Bold);Text("${team.league} • ${team.abbr}",color=FavMuted,fontSize=9.sp)}}}}}},confirmButton={Button(onClick={onDone(chosen.sortedBy{it.name})}){Text("SAVE ${chosen.size}",fontWeight=FontWeight.Black)}},dismissButton={TextButton(onClick={onDone(current)}){Text("CANCEL")}})}

private suspend fun loadFavoriteNews(teams:List<FavoriteTeam>):List<FavoriteNews>=withContext(Dispatchers.IO){teams.flatMap{team->runCatching{fetchNews(team)}.getOrDefault(emptyList())}.sortedByDescending{it.published}.take(18)}
private fun fetchNews(team:FavoriteTeam):List<FavoriteNews>{
    val path=when(team.league){"NFL"->"football/nfl";"NBA"->"basketball/nba";"MLB"->"baseball/mlb";"NHL"->"hockey/nhl";else->return emptyList()}
    val c=try{URL("https://site.api.espn.com/apis/site/v2/sports/$path/news?limit=50").openConnection() as HttpURLConnection}catch(_:Exception){return emptyList()}
    return try{c.connectTimeout=2200;c.readTimeout=4500;c.requestMethod="GET";c.setRequestProperty("User-Agent","XSportsX/1.7");if(c.responseCode !in 200..299)return emptyList();val a=JSONObject(c.inputStream.bufferedReader().use{it.readText()}).optJSONArray("articles")?:return emptyList();val out=ArrayList<FavoriteNews>();val tokens=listOf(team.name.lowercase(),team.abbr.lowercase());for(i in 0 until a.length()){val x=a.optJSONObject(i)?:continue;val h=x.optString("headline");val d=x.optString("description");if(tokens.any{"$h $d".lowercase().contains(it)})out+=FavoriteNews(team.abbr,h,d,x.optString("published"),x.optJSONObject("links")?.optString("web").orEmpty());if(out.size>=6)break};out}catch(_:Exception){emptyList()}finally{c.disconnect()}
}
