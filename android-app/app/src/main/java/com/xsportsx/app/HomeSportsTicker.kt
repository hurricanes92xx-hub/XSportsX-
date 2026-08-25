package com.xsportsx.app

import android.util.Xml
import androidx.compose.foundation.background
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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.*
import org.json.JSONObject
import org.xmlpull.v1.XmlPullParser
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
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

private fun dateString(offset:Int):String{
    val f=SimpleDateFormat("yyyyMMdd",Locale.US).apply{timeZone=TimeZone.getTimeZone("UTC")}
    val c=Calendar.getInstance(TimeZone.getTimeZone("UTC"));c.add(Calendar.DAY_OF_YEAR,offset);return f.format(c.time)
}
private fun dateRange()="${dateString(-1)}-${dateString(1)}"

private fun getBody(url:String,accept:String="*/*"):String?=try{
    val c=URL(url).openConnection() as HttpURLConnection
    c.connectTimeout=3500;c.readTimeout=6000;c.requestMethod="GET"
    c.setRequestProperty("User-Agent","XSportsX/1.7");c.setRequestProperty("Accept",accept)
    if(c.responseCode !in 200..299)null else c.inputStream.bufferedReader().use{it.readText()}
}catch(_:Exception){null}
private fun getJson(url:String)=getBody(url,"application/json")?.let{runCatching{JSONObject(it)}.getOrNull()}
private fun eventTime(e:JSONObject)=runCatching{java.time.Instant.parse(e.optString("date")).toEpochMilli()}.getOrDefault(0L)

private suspend fun loadLeague(l:TickerLeague)=withContext(Dispatchers.IO){
    val j=getJson("https://site.api.espn.com/apis/site/v2/sports/${l.sport}/${l.id}/scoreboard?dates=${dateRange()}&limit=50")
    val events=j?.optJSONArray("events");val cutoff=System.currentTimeMillis()-86400000L
    val items=buildList{
        if(events!=null)for(i in 0 until events.length()){
            val e=events.optJSONObject(i)?:continue
            val comp=e.optJSONArray("competitions")?.optJSONObject(0)?:continue
            val teams=comp.optJSONArray("competitors")?:continue
            var home="TBD";var away="TBD";var hs="";var ascore=""
            for(k in 0 until teams.length()){
                val t=teams.optJSONObject(k)?:continue;val tm=t.optJSONObject("team")
                val name=tm?.optString("abbreviation")?.ifBlank{tm.optString("shortDisplayName")}.orEmpty().ifBlank{"TBD"}
                if(t.optString("homeAway")=="home"){home=name;hs=t.optString("score")}else{away=name;ascore=t.optString("score")}
            }
            val st=comp.optJSONObject("status")?.optJSONObject("type");val state=st?.optString("state")?:"pre";val detail=st?.optString("shortDetail")?:""
            val ts=eventTime(e);val kind=when(state){"in"->"LIVE";"post"->if(ts==0L||ts>=cutoff)"FINAL" else "EXPIRED";else->"UPCOMING"}
            if(kind!="EXPIRED")add(TickerItem(kind,l.name,if(kind=="UPCOMING")"$away @ $home • $detail" else "$away $ascore  •  $home $hs",ts))
        }
    }
    TickerLeagueGroup(l.name,items.sortedBy{it.timestamp}.take(12))
}

private fun parseRss(xml:String):List<TickerItem>{
    val p=Xml.newPullParser();p.setInput(xml.reader());val out=mutableListOf<TickerItem>();var type=p.eventType;var inItem=false;var title="";var date=""
    while(type!=XmlPullParser.END_DOCUMENT){
        when(type){
            XmlPullParser.START_TAG->when{
                p.name.equals("item",true)->{inItem=true;title="";date=""}
                inItem&&p.name.equals("title",true)->title=p.nextText().trim()
                inItem&&(p.name.equals("pubDate",true)||p.name.equals("published",true))->date=p.nextText().trim()
            }
            XmlPullParser.END_TAG->if(p.name.equals("item",true)&&inItem){
                val ts=runCatching{SimpleDateFormat("EEE, dd MMM yyyy HH:mm:ss z",Locale.US).parse(date)?.time?:0L}.getOrDefault(0L)
                if(title.isNotBlank())out+=TickerItem("NEWS","GOOGLE",title,ts);inItem=false
            }
        };type=p.next()
    };return out
}

private suspend fun loadGoogleNews():List<TickerItem>=withContext(Dispatchers.IO){
    listOf(
        "NFL NBA MLB NHL WNBA", "college football college basketball MLS EPL UCL LaLiga Serie A Bundesliga Ligue 1",
        "UFC MMA boxing Formula 1 F1 NASCAR", "sports breaking news scores finals injuries trades"
    ).map{q->async{
        val u="https://news.google.com/rss/search?q=${URLEncoder.encode(q,"UTF-8")}&hl=en-US&gl=US&ceid=US:en"
        getBody(u,"application/rss+xml,application/xml,text/xml")?.let{parseRss(it)}?:emptyList()
    }}.awaitAll().flatten().filter{it.timestamp==0L||it.timestamp>=System.currentTimeMillis()-86400000L}
        .distinctBy{it.text.lowercase(Locale.US)}.sortedByDescending{it.timestamp}.take(12)
}

private suspend fun loadEspnNews():List<TickerItem>=withContext(Dispatchers.IO){
    val urls=listOf("https://site.api.espn.com/apis/site/v2/sports/news?region=us&lang=en&limit=12","https://site.api.espn.com/apis/site/v2/sports/general/news?region=us&lang=en&limit=12")
    val a=urls.asSequence().mapNotNull{getJson(it)?.optJSONArray("articles")}.firstOrNull()?:return@withContext emptyList()
    buildList{for(i in 0 until a.length()){val x=a.optJSONObject(i)?:continue;val h=x.optString("headline").trim();if(h.isBlank())continue;val ts=runCatching{java.time.Instant.parse(x.optString("published")).toEpochMilli()}.getOrDefault(0L);add(TickerItem("NEWS","ESPN",h,ts))}}.sortedByDescending{it.timestamp}.take(8)
}

private fun dbLeague(n:String):String?=when{
    n.contains("national football",true)||n.equals("NFL",true)->"NFL"
    n.contains("national basketball",true)||n.equals("NBA",true)->"NBA"
    n.contains("national hockey",true)||n.equals("NHL",true)->"NHL"
    n.contains("major league baseball",true)||n.equals("MLB",true)->"MLB"
    n.contains("WNBA",true)->"WNBA";n.contains("premier league",true)->"EPL";n.contains("champions league",true)->"UCL"
    n.contains("la liga",true)->"LaLiga";n.contains("serie a",true)->"Serie A";n.contains("bundesliga",true)->"Bundesliga";n.contains("ligue 1",true)->"Ligue 1";n.contains("major league soccer",true)->"MLS"
    n.contains("college football",true)||n.contains("ncaa football",true)->"NCAA FB";n.contains("college basketball",true)||n.contains("ncaa basketball",true)->"NCAA BB";else->null
}

private suspend fun loadSportsDbFallback():List<TickerLeagueGroup>=withContext(Dispatchers.IO){
    // Rescue score/schedule source only. Normal operation stays on ESPN for speed.
    listOf(-1,0,1).map{offset->async{
        val j=getJson("https://www.thesportsdb.com/api/v1/json/123/eventsday.php?d=${dateString(offset)}");val es=j?.optJSONArray("events")?:return@async emptyList<TickerItem>()
        buildList{for(i in 0 until es.length()){
            val e=es.optJSONObject(i)?:continue;val league=dbLeague(e.optString("strLeague"))?:continue
            val home=e.optString("strHomeTeam").ifBlank{"TBD"};val away=e.optString("strAwayTeam").ifBlank{"TBD"};val hs=e.optString("intHomeScore");val ascore=e.optString("intAwayScore");val status=e.optString("strStatus")
            val ts=runCatching{SimpleDateFormat("yyyy-MM-dd HH:mm:ss",Locale.US).apply{timeZone=TimeZone.getTimeZone("UTC")}.parse("${e.optString("dateEvent")} ${e.optString("strTime")}")?.time?:0L}.getOrDefault(0L)
            val kind=when{status.contains("live",true)||status.contains("progress",true)->"LIVE";hs.isNotBlank()&&ascore.isNotBlank()&&offset<=0->"FINAL";else->"UPCOMING"}
            add(TickerItem(kind,league,if(kind=="UPCOMING")"$away @ $home" else "$away $ascore  •  $home $hs",ts))
        }}
    }}.awaitAll().flatten().groupBy{it.league}.map{(l,items)->TickerLeagueGroup(l,items.sortedBy{it.timestamp}.take(12))}
}

private suspend fun loadTickerGroups():List<TickerLeagueGroup>=coroutineScope{
    val espn=tickerLeagues.map{async{loadLeague(it)}}.awaitAll().filter{it.items.isNotEmpty()}
    val scores=if(espn.isEmpty())async{loadSportsDbFallback()} else null
    val news=async{(loadGoogleNews()+loadEspnNews()).distinctBy{it.text.lowercase(Locale.US)}.sortedByDescending{it.timestamp}.take(14)}
    (if(espn.isNotEmpty())espn else scores?.await().orEmpty())+news.await().let{if(it.isEmpty())emptyList()else listOf(TickerLeagueGroup("BREAKING NEWS",it))}
}

@Composable
fun HomeSportsTicker(modifier:Modifier=Modifier){
    var groups by remember{mutableStateOf<List<TickerLeagueGroup>>(emptyList())};var index by remember{mutableIntStateOf(0)};var loading by remember{mutableStateOf(true)}
    LaunchedEffect(Unit){while(isActive){loading=true;val loaded=runCatching{loadTickerGroups()}.getOrDefault(emptyList());if(loaded.isNotEmpty())groups=loaded;index=0;loading=false;delay(60000)}}
    LaunchedEffect(groups){while(isActive&&groups.isNotEmpty()){delay(6000);index=(index+1)%groups.size}}
    val group=groups.getOrNull(index);val items=group?.items?:listOf(TickerItem("NEWS","XSPORTSX",if(loading)"Connecting to sports feeds…" else "Waiting for backup sports feeds…"))
    Box(modifier.fillMaxWidth().height(72.dp).background(Color(0xF2080A10)),contentAlignment=Alignment.CenterStart){
        Row(Modifier.fillMaxSize(),verticalAlignment=Alignment.CenterVertically){
            Box(Modifier.padding(start=10.dp,end=8.dp).clip(RoundedCornerShape(8.dp)).background(Color(0xFF111722)).padding(horizontal=11.dp,vertical=8.dp)){Text("X",color=Color(0xFFFF1744),fontSize=20.sp,fontWeight=FontWeight.Black)}
            Text(group?.league?:"SPORTS",color=Color.White,fontSize=11.sp,fontWeight=FontWeight.Black,modifier=Modifier.padding(end=10.dp))
            LazyRow(Modifier.weight(1f),horizontalArrangement=Arrangement.spacedBy(14.dp),contentPadding=PaddingValues(end=14.dp)){items(items){item->
                val accent=when(item.kind){"LIVE"->Color(0xFFFF1744);"FINAL"->Color(0xFFB7C1D1);"NEWS"->Color(0xFFFFC107);else->Color(0xFF8D99AE)}
                Row(verticalAlignment=Alignment.CenterVertically){Text(item.kind,color=accent,fontSize=9.sp,fontWeight=FontWeight.Black);Spacer(Modifier.width(7.dp));Text(item.text,color=Color(0xFFE5E9F0),fontSize=12.sp,fontWeight=FontWeight.SemiBold,maxLines=1)}
            }}
        }
    }
}
