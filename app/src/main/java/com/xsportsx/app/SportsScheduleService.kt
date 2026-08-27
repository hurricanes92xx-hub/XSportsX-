package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private data class ScheduleLeague(val league:String,val sport:String,val path:String,val officialUrl:String)

object SportsScheduleService {
    private const val DAYS_AHEAD = 30
    private const val MAX_GAMES_PER_LEAGUE = 100
    private val leagues = listOf(
        ScheduleLeague("NFL","Football","football/nfl","https://www.nfl.com/"),
        ScheduleLeague("NBA","Basketball","basketball/nba","https://www.nba.com/"),
        ScheduleLeague("NCAA FB","Football","football/college-football","https://www.ncaa.com/sports/football/fbs"),
        ScheduleLeague("NCAA FCS","Football","football/college-football","https://www.ncaa.com/sports/football/fcs"),
        ScheduleLeague("NCAA BB","Basketball","basketball/mens-college-basketball","https://www.ncaa.com/sports/basketball-men/d1"),
        ScheduleLeague("NCAA WBB","Basketball","basketball/womens-college-basketball","https://www.ncaa.com/sports/basketball-women/d1"),
        ScheduleLeague("MLB","Baseball","baseball/mlb","https://www.mlb.com/"),
        ScheduleLeague("NHL","Hockey","hockey/nhl","https://www.nhl.com/"),
        ScheduleLeague("UFC","MMA","mma/ufc","https://www.ufc.com/"),
        ScheduleLeague("BOXING","Boxing","boxing/boxing","https://www.boxing.com/")
    )

    fun normalizeLeague(label:String):String=when(label.trim().uppercase()){
        "COLLEGE FOOTBALL","NCAA FOOTBALL","NCAAF"->"NCAA FB"
        "COLLEGE BASKETBALL","NCAA MEN","NCAAM"->"NCAA BB"
        "NCAA WOMEN","NCAAW"->"NCAA WBB"
        "COLLEGE BASEBALL"->"NCAA BASEBALL"
        "COLLEGE SOFTBALL"->"NCAA SOFTBALL"
        "COLLEGE MEN'S HOCKEY"->"NCAA MEN HOCKEY"
        "COLLEGE WOMEN'S HOCKEY"->"NCAA WOMEN HOCKEY"
        "COLLEGE WOMEN'S LACROSSE"->"NCAA WOMEN LAX"
        "COLLEGE WRESTLING"->"NCAA WRESTLING"
        "COLLEGE MEN'S SOCCER"->"NCAA MEN SOCCER"
        "COLLEGE WOMEN'S SOCCER"->"NCAA WOMEN SOCCER"
        "FORMULA 1","FORMULA1"->"F1"
        "MOTO GP","MOTOGP"->"MOTOGP"
        "FORMULA E","FORMULAE"->"FORMULA E"
        "MONSTER JAM","MONSTERJAM"->"MONSTER JAM"
        else -> label.trim().uppercase()
    }

    fun canonicalLeagueFor(label:String):String = normalizeLeague(label)

    val uiLeagueChoices:List<String> = listOf("NFL","NBA","NCAA FB","NCAA FCS","NCAA BB","NCAA WBB","MLB","NCAA BASEBALL","NHL","NCAA MEN HOCKEY","NCAA WOMEN HOCKEY","NCAA SOFTBALL","UFC","BOXING","NCAA VB","NCAA MEN SOCCER","NCAA WOMEN SOCCER","NCAA MEN LAX","NCAA WOMEN LAX","NCAA WRESTLING","MLS","EPL","LaLiga","Bundesliga","Serie A","Ligue 1","UCL","UEL","NWSL","RUGBY","WRESTLING","MOTOGP","WRC","WEC","IMSA","FORMULA E","MXGP","MONSTER JAM","F1","NASCAR","INDYCAR")

    suspend fun load():List<SportsEvent> = withContext(Dispatchers.IO) {
        val today=LocalDate.now(ZoneId.systemDefault())
        val end=today.plusDays(DAYS_AHEAD.toLong())
        val dates="${today.format(DateTimeFormatter.BASIC_ISO_DATE)}-${end.format(DateTimeFormatter.BASIC_ISO_DATE)}"
        val limiter=Semaphore(8)
        val results=withTimeout(28_000L){
            coroutineScope{
                leagues.map{league->async{limiter.withPermit{fetchLeagueWithFallbacks(league,dates)}}}.awaitAll()
            }
        }
        results.flatten().distinctBy{it.id.ifBlank{it.title+it.startUtc+it.league}}
            .filter{it.isLive||it.isPregame()||it.isUpcoming}
            .sortedWith(compareBy<SportsEvent>{!(it.isLive||it.isPregame())}.thenBy{it.startUtc})
    }

    private suspend fun fetchLeagueWithFallbacks(league:ScheduleLeague,dates:String):List<SportsEvent>{
        val primary=runCatching{fetchEspn(league,dates)}.getOrDefault(emptyList())
        val fallback=if(primary.isEmpty())runCatching{fetchEspnV3(league,dates)}.getOrDefault(emptyList())else emptyList()
        return (primary+fallback).filter{it.league.equals(league.league,true)}.map{it.copy(sourceUrl=it.sourceUrl.ifBlank{league.officialUrl})}.distinctBy{canonicalKey(it)}.sortedBy{it.startUtc}.take(MAX_GAMES_PER_LEAGUE)
    }
    private fun canonicalKey(e:SportsEvent):String=listOf(e.league,normalize(e.home),normalize(e.away),e.startUtc.take(10)).joinToString("|")
    private fun normalize(v:String):String=v.lowercase().replace("fc"," ").replace("  "," ").trim()
    private fun fetchEspn(league:ScheduleLeague,dates:String):List<SportsEvent> = parseEspn(JSONObject(http("https://site.api.espn.com/apis/site/v2/sports/${league.path}/scoreboard?dates=$dates&limit=1000")),league)
    private fun fetchEspnV3(league:ScheduleLeague,dates:String):List<SportsEvent> = parseEspn(JSONObject(http("https://site.api.espn.com/apis/site/v3/sports/${league.path}/scoreboard?dates=$dates&limit=1000")),league)

    private fun parseEspn(root:JSONObject,league:ScheduleLeague):List<SportsEvent>{
        val events=root.optJSONArray("events")?:root.optJSONObject("content")?.optJSONArray("events")?:return emptyList();val out=ArrayList<SportsEvent>(events.length())
        for(i in 0 until events.length()){
            val e=events.optJSONObject(i)?:continue;val competition=e.optJSONArray("competitions")?.optJSONObject(0)?:continue;val competitors=competition.optJSONArray("competitors")?:continue
            var home="";var away="";var homeLogo="";var awayLogo=""
            for(j in 0 until competitors.length()){
                val c=competitors.optJSONObject(j)?:continue;val team=c.optJSONObject("team");val name=team?.optString("displayName")?.ifBlank{team.optString("shortDisplayName")}?:c.optString("displayName");val logo=team?.optString("logo").orEmpty()
                if(c.optString("homeAway").equals("home",true)){home=name;homeLogo=logo}else{away=name;awayLogo=logo}
            }
            val status=competition.optJSONObject("status")?:e.optJSONObject("status")?:JSONObject();val type=status.optJSONObject("type")?:JSONObject();val state=type.optString("state").ifBlank{status.optString("state")};val detail=type.optString("shortDetail").ifBlank{type.optString("detail")}
            val broadcasts=competition.optJSONArray("broadcasts");val broadcast=buildString{if(broadcasts!=null)for(j in 0 until broadcasts.length()){val names=broadcasts.optJSONObject(j)?.optJSONArray("names");if(names!=null)for(k in 0 until names.length()){if(isNotEmpty())append(", ");append(names.optString(k))}}}
            val start=e.optString("date").ifBlank{competition.optString("startDate")};val rawName=e.optString("name").ifBlank{e.optString("shortName")};val title=rawName.ifBlank{listOf(home,away).filter{it.isNotBlank()}.joinToString(" vs ")}
            val youtube=e.optString("youtubeVideoId").ifBlank{e.optString("youtubeUrl")}.ifBlank{league.officialUrl}.let{extractYouTubeId(it)}
            out+=SportsEvent(e.optString("id"),league.sport,league.league,title,start,detail,state,home,away,homeLogo,awayLogo,broadcast,e.optString("image"),league.officialUrl,youtube)
        }
        return out
    }
    private fun extractYouTubeId(value:String):String{val v=value.trim();if(v.matches(Regex("[A-Za-z0-9_-]{11}")))return v;return Regex("(?:v=|youtu\\.be/|youtube\\.com/(?:embed/|shorts/))([A-Za-z0-9_-]{11})").find(v)?.groupValues?.getOrNull(1).orEmpty()}
    private fun http(target:String):String{val c=(URL(target).openConnection()as HttpURLConnection).apply{requestMethod="GET";connectTimeout=2200;readTimeout=4500;instanceFollowRedirects=true;setRequestProperty("User-Agent","XSportsX/1.5 (Android)");setRequestProperty("Accept","application/json,text/plain,*/*")};return try{val code=c.responseCode;if(code !in 200..299)error("Schedule HTTP $code");c.inputStream.bufferedReader(Charsets.UTF_8).use{it.readText()}}finally{c.disconnect()}}
}
