package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter

data class SportsEvent(
    val id:String,val sport:String,val league:String,val title:String,val startUtc:String,
    val status:String,val state:String,val home:String,val away:String,val homeLogo:String,
    val awayLogo:String,val broadcast:String,val artUrl:String="",val sourceUrl:String="",
    val youtubeVideoId:String=""
) {
    val isLive:Boolean get()=state.equals("in",true)||state.equals("live",true)||status.contains("live",true)
    val isUpcoming:Boolean get()=state.equals("pre",true)||state.equals("scheduled",true)||state.equals("upcoming",true)
    val searchText:String get()=listOf(home,away,title,league,broadcast).joinToString(" ")
}

data class ScheduleLeague(val sport:String,val league:String,val path:String,val officialUrl:String="")

object SportsScheduleService {
    private val leagues=listOf(
        ScheduleLeague("Football","NFL","football/nfl","https://www.nfl.com/schedules/"),
        ScheduleLeague("College Football","NCAA FB","football/college-football","https://www.ncaa.com/scoreboard/football/fbs"),
        ScheduleLeague("College Football","NCAA FCS","football/college-football","https://www.ncaa.com/scoreboard/football/fcs"),
        ScheduleLeague("Basketball","NBA","basketball/nba","https://www.nba.com/schedule"),
        ScheduleLeague("Basketball","WNBA","basketball/wnba","https://www.wnba.com/schedule"),
        ScheduleLeague("College Basketball","NCAA BB","basketball/mens-college-basketball","https://www.ncaa.com/scoreboard/basketball-men/d1"),
        ScheduleLeague("College Basketball","NCAA WBB","basketball/womens-college-basketball","https://www.ncaa.com/scoreboard/basketball-women/d1"),
        ScheduleLeague("Baseball","MLB","baseball/mlb","https://www.mlb.com/schedule"),
        ScheduleLeague("College Baseball","NCAA BASEBALL","baseball/college-baseball","https://www.ncaa.com/sports/baseball/d1"),
        ScheduleLeague("Hockey","NHL","hockey/nhl","https://www.nhl.com/schedule"),
        ScheduleLeague("College Hockey","NCAA MEN HOCKEY","hockey/college-hockey","https://www.ncaa.com/sports/icehockey-men/d1"),
        ScheduleLeague("College Hockey","NCAA WOMEN HOCKEY","hockey/college-hockey-women","https://www.ncaa.com/sports/icehockey-women"),
        ScheduleLeague("College Softball","NCAA SOFTBALL","softball/college-softball","https://www.ncaa.com/sports/softball/d1"),
        ScheduleLeague("Soccer","MLS","soccer/usa.1","https://www.mlssoccer.com/schedule"),
        ScheduleLeague("Soccer","EPL","soccer/eng.1","https://www.premierleague.com/fixtures"),
        ScheduleLeague("Soccer","LaLiga","soccer/esp.1","https://www.laliga.com/en-GB/laliga-easports/results"),
        ScheduleLeague("Soccer","Bundesliga","soccer/ger.1","https://www.bundesliga.com/en/bundesliga/matchday"),
        ScheduleLeague("Soccer","Serie A","soccer/ita.1","https://www.legaseriea.it/en"),
        ScheduleLeague("Soccer","Ligue 1","soccer/fra.1","https://www.ligue1.com/"),
        ScheduleLeague("Soccer","UCL","soccer/uefa.champions","https://www.uefa.com/uefachampionsleague/fixtures-results/"),
        ScheduleLeague("Soccer","UEL","soccer/uefa.europa","https://www.uefa.com/uefaeuropaleague/fixtures-results/"),
        ScheduleLeague("Soccer","NWSL","soccer/usa.nwsl","https://www.nwslsoccer.com/schedule"),
        ScheduleLeague("College Soccer","NCAA MEN SOCCER","soccer/college-soccer-men","https://www.ncaa.com/sports/soccer-men/d1"),
        ScheduleLeague("College Soccer","NCAA WOMEN SOCCER","soccer/college-soccer-women","https://www.ncaa.com/sports/soccer-women/d1"),
        ScheduleLeague("Rugby","RUGBY","rugby/rugby-union","https://www.world.rugby/fixtures"),
        ScheduleLeague("College Volleyball","NCAA VB","volleyball/womens-college-volleyball","https://www.ncaa.com/scoreboard/volleyball-women"),
        ScheduleLeague("College Lacrosse","NCAA MEN LAX","lacrosse/college-men","https://www.ncaa.com/sports/lacrosse-men/d1"),
        ScheduleLeague("College Lacrosse","NCAA WOMEN LAX","lacrosse/college-women","https://www.ncaa.com/sports/lacrosse-women/d1"),
        ScheduleLeague("College Wrestling","NCAA WRESTLING","wrestling/college-wrestling","https://www.ncaa.com/sports/wrestling/d1"),
        ScheduleLeague("Racing","F1","racing/f1","https://www.formula1.com/en/racing/2026"),
        ScheduleLeague("Racing","NASCAR","racing/nascar-premier","https://www.nascar.com/schedule/"),
        ScheduleLeague("Racing","INDYCAR","racing/irl","https://www.indycar.com/schedule"),
        ScheduleLeague("MMA","UFC","mma/ufc","https://www.ufc.com/events"),
        ScheduleLeague("Boxing","BOXING","boxing/boxing","https://www.wbcboxing.com/en/eventos/list/")
    )

    fun canonicalLeagueFor(label:String):String = when(label.trim().uppercase()) {
        "NCAAF","COLLEGE FOOTBALL","NCAA FBS" -> "NCAA FB"
        "NCAA FCS" -> "NCAA FCS"
        "NCAAB","COLLEGE BASKETBALL","NCAA MEN'S BASKETBALL" -> "NCAA BB"
        "NCAA WOMEN'S BASKETBALL","COLLEGE WOMEN'S BASKETBALL" -> "NCAA WBB"
        "COLLEGE BASEBALL" -> "NCAA BASEBALL"
        "COLLEGE SOFTBALL" -> "NCAA SOFTBALL"
        "COLLEGE VOLLEYBALL","NCAA WOMEN'S VOLLEYBALL" -> "NCAA VB"
        "COLLEGE MEN'S LACROSSE" -> "NCAA MEN LAX"
        "COLLEGE WOMEN'S LACROSSE" -> "NCAA WOMEN LAX"
        "COLLEGE WRESTLING" -> "NCAA WRESTLING"
        "COLLEGE MEN'S SOCCER" -> "NCAA MEN SOCCER"
        "COLLEGE WOMEN'S SOCCER" -> "NCAA WOMEN SOCCER"
        "FORMULA 1","FORMULA1" -> "F1"
        "MOTO GP","MOTOGP" -> "MOTOGP"
        "FORMULA E","FORMULAE" -> "FORMULA E"
        "MONSTER JAM","MONSTERJAM" -> "MONSTER JAM"
        else -> label.trim().uppercase()
    }

    val uiLeagueChoices:List<String> = listOf("NFL","NBA","NCAA FB","NCAA FCS","NCAA BB","NCAA WBB","MLB","NCAA BASEBALL","NHL","NCAA MEN HOCKEY","NCAA WOMEN HOCKEY","NCAA SOFTBALL","UFC","BOXING","NCAA VB","NCAA MEN SOCCER","NCAA WOMEN SOCCER","NCAA MEN LAX","NCAA WOMEN LAX","NCAA WRESTLING","MLS","EPL","LaLiga","Bundesliga","Serie A","Ligue 1","UCL","UEL","NWSL","RUGBY","WRESTLING","MOTOGP","WRC","WEC","IMSA","FORMULA E","MXGP","MONSTER JAM","F1","NASCAR","INDYCAR")

    suspend fun load():List<SportsEvent> = withContext(Dispatchers.IO) {
        val today=LocalDate.now(ZoneId.systemDefault());val end=today.plusDays(30);val dates="${today.format(DateTimeFormatter.BASIC_ISO_DATE)}-${end.format(DateTimeFormatter.BASIC_ISO_DATE)}";val limiter=Semaphore(8)
        val results=withTimeout(28_000L){coroutineScope{leagues.map{league->async{limiter.withPermit{fetchLeagueWithFallbacks(league,dates)}}}.awaitAll()}}
        results.flatten().distinctBy{it.id.ifBlank{it.title+it.startUtc+it.league}}.filter{it.isLive||it.isUpcoming}.sortedWith(compareBy<SportsEvent>{!it.isLive}.thenBy{it.startUtc})
    }
    private suspend fun fetchLeagueWithFallbacks(league:ScheduleLeague,dates:String):List<SportsEvent>{val primary=runCatching{fetchEspn(league,dates)}.getOrDefault(emptyList());val fallback=if(primary.isEmpty())runCatching{fetchEspnV3(league,dates)}.getOrDefault(emptyList())else emptyList();return (primary+fallback).filter{it.league.equals(league.league,true)}.map{it.copy(sourceUrl=it.sourceUrl.ifBlank{league.officialUrl})}.distinctBy{canonicalKey(it)}}
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
            val youtube = e.optString("youtubeVideoId").ifBlank { e.optString("youtubeUrl") }.ifBlank { league.officialUrl }.let { extractYouTubeId(it) }
            out+=SportsEvent(e.optString("id"),league.sport,league.league,title,start,detail,state,home,away,homeLogo,awayLogo,broadcast,e.optString("image"),league.officialUrl,youtube)
        }
        return out
    }
    private fun extractYouTubeId(value:String):String{val v=value.trim();if(v.matches(Regex("[A-Za-z0-9_-]{11}")))return v;return Regex("(?:v=|youtu\\.be/|youtube\\.com/(?:embed/|shorts/))([A-Za-z0-9_-]{11})").find(v)?.groupValues?.getOrNull(1).orEmpty()}
    private fun http(target:String):String{val c=(URL(target).openConnection()as HttpURLConnection).apply{requestMethod="GET";connectTimeout=2200;readTimeout=4500;instanceFollowRedirects=true;setRequestProperty("User-Agent","XSportsX/1.5 (Android)");setRequestProperty("Accept","application/json,text/plain,*/*")};return try{val code=c.responseCode;if(code !in 200..299)error("Schedule HTTP $code");c.inputStream.bufferedReader(Charsets.UTF_8).use{it.readText()}}finally{c.disconnect()}}
}
