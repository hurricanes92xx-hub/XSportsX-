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
    val awayLogo:String,val broadcast:String,val artUrl:String="",val sourceUrl:String=""
) {
    val isLive:Boolean get()=state.equals("in",true)||state.equals("live",true)||status.contains("live",true)
    val isUpcoming:Boolean get()=state.equals("pre",true)||state.equals("scheduled",true)||state.equals("upcoming",true)
    val searchText:String get()=listOf(home,away,title,league,broadcast).joinToString(" ")
}

data class ScheduleLeague(val sport:String,val league:String,val path:String)

object SportsScheduleService {
    private val leagues=listOf(
        ScheduleLeague("Football","NFL","football/nfl"),
        ScheduleLeague("College Football","NCAA","football/college-football"),
        ScheduleLeague("Basketball","NBA","basketball/nba"),
        ScheduleLeague("Basketball","WNBA","basketball/wnba"),
        ScheduleLeague("College Basketball","NCAA","basketball/mens-college-basketball"),
        ScheduleLeague("Baseball","MLB","baseball/mlb"),
        ScheduleLeague("Hockey","NHL","hockey/nhl"),
        ScheduleLeague("Soccer","MLS","soccer/usa.1"),
        ScheduleLeague("Soccer","EPL","soccer/eng.1"),
        ScheduleLeague("Soccer","LaLiga","soccer/esp.1"),
        ScheduleLeague("Soccer","Bundesliga","soccer/ger.1"),
        ScheduleLeague("Soccer","Serie A","soccer/ita.1"),
        ScheduleLeague("Soccer","Ligue 1","soccer/fra.1"),
        ScheduleLeague("Soccer","UCL","soccer/uefa.champions"),
        ScheduleLeague("Soccer","UEL","soccer/uefa.europa"),
        ScheduleLeague("Soccer","NWSL","soccer/usa.nwsl"),
        ScheduleLeague("Racing","F1","racing/f1")
    )

    suspend fun load():List<SportsEvent> = withContext(Dispatchers.IO) {
        val today=LocalDate.now(ZoneId.systemDefault())
        val dates=(0L..3L).map { today.plusDays(it) }
        val limiter=Semaphore(8)
        val results=withTimeout(15_000L) {
            coroutineScope {
                leagues.flatMap { league -> dates.map { date ->
                    async { limiter.withPermit { runCatching { fetchLeague(league,date) }.getOrElse { emptyList() } } }
                } }.awaitAll()
            }
        }
        val events=results.flatten()
            .distinctBy { it.id.ifBlank { it.title+it.startUtc+it.league } }
            .filter { it.isLive || it.isUpcoming }
            .sortedWith(compareBy<SportsEvent>{ !it.isLive }.thenBy { it.startUtc })
        if(events.isEmpty()) error("Schedule providers returned no events. Check internet access and tap REFRESH.")
        events
    }

    private fun fetchLeague(league:ScheduleLeague,date:LocalDate):List<SportsEvent> {
        val dateText=date.format(DateTimeFormatter.BASIC_ISO_DATE)
        val primary="https://site.api.espn.com/apis/site/v2/sports/${league.path}/scoreboard?dates=$dateText&limit=500"
        val v3="https://site.api.espn.com/apis/site/v3/sports/${league.path}/scoreboard?dates=$dateText&limit=500"
        val urls=mutableListOf(primary,v3)
        val sport=league.path.substringBefore('/')
        val code=league.path.substringAfterLast('/')
        urls += "https://cdn.espn.com/core/$sport/scoreboard?xhr=1&league=${encode(code)}&dates=$dateText"
        for(url in urls) {
            try {
                val parsed=parse(JSONObject(http(url)),league)
                if(parsed.isNotEmpty()) return parsed
            } catch (_:Throwable) { }
        }
        return emptyList()
    }

    private fun parse(root:JSONObject,league:ScheduleLeague):List<SportsEvent> {
        val events=root.optJSONArray("events") ?: root.optJSONObject("content")?.optJSONArray("events") ?: return emptyList()
        val out=ArrayList<SportsEvent>(events.length())
        for(i in 0 until events.length()) {
            val e=events.optJSONObject(i) ?: continue
            val competition=e.optJSONArray("competitions")?.optJSONObject(0) ?: continue
            val competitors=competition.optJSONArray("competitors") ?: continue
            var home="";var away="";var homeLogo="";var awayLogo=""
            for(j in 0 until competitors.length()) {
                val c=competitors.optJSONObject(j) ?: continue
                val team=c.optJSONObject("team") ?: continue
                val name=team.optString("displayName").ifBlank { team.optString("shortDisplayName") }
                val logo=team.optString("logo").ifBlank { team.optJSONArray("logos")?.optJSONObject(0)?.optString("href") ?: "" }
                if(c.optString("homeAway").equals("home",true)){home=name;homeLogo=logo} else {away=name;awayLogo=logo}
            }
            val status=competition.optJSONObject("status") ?: e.optJSONObject("status") ?: JSONObject()
            val type=status.optJSONObject("type") ?: JSONObject()
            val state=type.optString("state").ifBlank { status.optString("state") }
            val detail=type.optString("shortDetail").ifBlank { type.optString("detail") }.ifBlank { status.optString("displayClock") }
            val broadcasts=competition.optJSONArray("broadcasts")
            val broadcast=buildString {
                if(broadcasts!=null) for(j in 0 until broadcasts.length()) {
                    val b=broadcasts.optJSONObject(j) ?: continue
                    val names=b.optJSONArray("names")
                    if(names!=null) for(k in 0 until names.length()) { if(isNotEmpty()) append(", "); append(names.optString(k)) }
                }
            }
            val start=e.optString("date").ifBlank { competition.optString("startDate") }
            out += SportsEvent(e.optString("id"),league.sport,league.league,e.optString("name").ifBlank { e.optString("shortName") },start,detail,state,home,away,homeLogo,awayLogo,broadcast,e.optString("image"))
        }
        return out
    }

    private fun encode(value:String):String=java.net.URLEncoder.encode(value,"UTF-8")

    private fun http(target:String):String {
        val c=(URL(target).openConnection() as HttpURLConnection).apply {
            requestMethod="GET";connectTimeout=2500;readTimeout=4500;instanceFollowRedirects=true
            setRequestProperty("User-Agent","XSportsX/1.4")
            setRequestProperty("Accept","application/json,text/plain,*/*")
            setRequestProperty("Cache-Control","no-cache")
        }
        return try {
            val code=c.responseCode
            if(code !in 200..299) error("Schedule HTTP $code")
            c.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        } finally { c.disconnect() }
    }
}
