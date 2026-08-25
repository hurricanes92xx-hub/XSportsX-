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

data class ScheduleLeague(val sport:String,val league:String,val path:String,val officialUrl:String="")

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
        ScheduleLeague("Racing","F1","racing/f1"),
        ScheduleLeague("MMA","UFC","mma/ufc","https://www.ufc.com/events"),
        ScheduleLeague("Boxing","BOXING","boxing/boxing","https://wbcboxing.com/en/eventos/list/")
    )

    suspend fun load():List<SportsEvent> = withContext(Dispatchers.IO) {
        val today=LocalDate.now(ZoneId.systemDefault())
        val end=today.plusDays(30)
        val dates="${today.format(DateTimeFormatter.BASIC_ISO_DATE)}-${end.format(DateTimeFormatter.BASIC_ISO_DATE)}"
        // 19 leagues in parallel, capped below the point where the device or
        // ESPN starts queueing connections. This replaces the old 76-call loop.
        val limiter=Semaphore(10)

        val results=withTimeout(25_000L) {
            coroutineScope {
                leagues.map { league ->
                    async {
                        limiter.withPermit {
                            runCatching { fetchLeague(league,dates) }.getOrElse { emptyList() }
                        }
                    }
                }.awaitAll()
            }
        }

        results.flatten()
            .distinctBy { it.id.ifBlank { it.title+it.startUtc+it.league } }
            .filter { it.isLive || it.isUpcoming }
            .sortedWith(compareBy<SportsEvent>{ !it.isLive }.thenBy { it.startUtc })
    }

    private fun fetchLeague(league:ScheduleLeague,dates:String):List<SportsEvent> {
        val primary="https://site.api.espn.com/apis/site/v2/sports/${league.path}/scoreboard?dates=$dates&limit=1000"
        val v3="https://site.api.espn.com/apis/site/v3/sports/${league.path}/scoreboard?dates=$dates&limit=1000"
        // Keep fallback count low: the primary endpoint is public and the v3
        // endpoint is the only useful alternate. Extra CDN retries were a major
        // contributor to the old timeout on slower mobile connections.
        for(url in listOf(primary,v3)) {
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
                val team=c.optJSONObject("team")
                val athlete=c.optJSONObject("athlete")
                val name=team?.optString("displayName")?.ifBlank { team.optString("shortDisplayName") }
                    ?: athlete?.optString("displayName")?.ifBlank { athlete.optString("shortName") }
                    ?: c.optString("displayName")
                val logo=team?.optString("logo")?.ifBlank { team.optJSONArray("logos")?.optJSONObject(0)?.optString("href") ?: "" } ?: ""
                if(c.optString("homeAway").equals("home",true)){home=name;homeLogo=logo} else {away=name;awayLogo=logo}
            }
            val rawName=e.optString("name").ifBlank { e.optString("shortName") }
            if(league.sport=="MMA" || league.sport=="Boxing") {
                if(home.isBlank() && away.isBlank()) {
                    val parts=rawName.split(" vs "," vs. "," at ",ignoreCase=true,limit=2)
                    if(parts.size==2){home=parts[0].trim();away=parts[1].trim()}
                }
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
            val official=when(league.league){"UFC"->"https://www.ufc.com/events";"BOXING"->"https://wbcboxing.com/en/eventos/list/";else->league.officialUrl}
            val title=rawName.ifBlank { listOf(home,away).filter { it.isNotBlank() }.joinToString(" vs ") }
            out += SportsEvent(e.optString("id"),league.sport,league.league,title,start,detail,state,home,away,homeLogo,awayLogo,broadcast,e.optString("image"),official)
        }
        return out
    }

    private fun http(target:String):String {
        val c=(URL(target).openConnection() as HttpURLConnection).apply {
            requestMethod="GET"
            connectTimeout=2500
            readTimeout=5000
            instanceFollowRedirects=true
            setRequestProperty("User-Agent","XSportsX/1.4 (Android)")
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
