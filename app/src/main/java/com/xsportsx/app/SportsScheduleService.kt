package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.LocalDate
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

data class SportsEvent(
    val id:String,
    val sport:String,
    val league:String,
    val title:String,
    val startUtc:String,
    val status:String,
    val state:String,
    val home:String,
    val away:String,
    val homeLogo:String,
    val awayLogo:String,
    val broadcast:String,
    val artUrl:String="",
    val sourceUrl:String=""
) {
    val isLive:Boolean get()=state.equals("in", true)||state.equals("live", true)
    val isUpcoming:Boolean get()=state.equals("pre", true)||state.equals("scheduled", true)
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
        val today=LocalDate.now(ZoneOffset.UTC)
        val dates=(0..14).map { today.plusDays(it.toLong()) }
        val limiter=Semaphore(6)
        val results=coroutineScope {
            leagues.flatMap { league ->
                dates.map { date ->
                    async {
                        limiter.withPermit {
                            runCatching { fetchLeague(league,date) }.getOrElse { emptyList() }
                        }
                    }
                }
            }.awaitAll()
        }

        val events=results.flatten()
            .distinctBy { it.id.ifBlank { it.title+it.startUtc+it.league } }
            .filter { it.isLive || it.isUpcoming }
            .sortedWith(compareBy<SportsEvent>{ !it.isLive }.thenBy { it.startUtc })

        if (events.isEmpty()) {
            error("No schedule data returned. Check network/API access and try REFRESH.")
        }
        events
    }

    private fun fetchLeague(league:ScheduleLeague,date:LocalDate):List<SportsEvent> {
        val dateText=date.format(DateTimeFormatter.BASIC_ISO_DATE)
        val endpoint="https://site.api.espn.com/apis/site/v2/sports/${league.path}/scoreboard?dates=$dateText&limit=500"
        val root=JSONObject(httpWithRetry(endpoint))
        val events=root.optJSONArray("events") ?: return emptyList()
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
                val logo=team.optString("logo")
                if(c.optString("homeAway").equals("home",true)) {
                    home=name;homeLogo=logo
                } else {
                    away=name;awayLogo=logo
                }
            }

            val status=competition.optJSONObject("status") ?: e.optJSONObject("status") ?: JSONObject()
            val type=status.optJSONObject("type") ?: JSONObject()
            val state=type.optString("state").ifBlank { status.optString("state") }
            val detail=type.optString("shortDetail").ifBlank { type.optString("detail") }
            val start=e.optString("date").ifBlank { competition.optString("startDate") }

            out += SportsEvent(
                id=e.optString("id"),sport=league.sport,league=league.league,
                title=e.optString("name").ifBlank { e.optString("shortName") },
                startUtc=start,status=detail,state=state,
                home=home,away=away,homeLogo=homeLogo,awayLogo=awayLogo,
                broadcast=competition.optString("broadcast"),artUrl=e.optString("image")
            )
        }
        return out
    }

    private fun httpWithRetry(target:String):String {
        var lastError:Throwable?=null
        repeat(3) { attempt ->
            try {
                val c=(URL(target).openConnection() as HttpURLConnection).apply {
                    requestMethod="GET";connectTimeout=7000;readTimeout=12000;instanceFollowRedirects=true
                    setRequestProperty("User-Agent","XSportsX/1.2")
                    setRequestProperty("Accept","application/json")
                    setRequestProperty("Cache-Control","no-cache")
                }
                return try {
                    val code=c.responseCode
                    if(code !in 200..299) error("Schedule HTTP $code")
                    c.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
                } finally { c.disconnect() }
            } catch(t:Throwable) {
                lastError=t
                if(attempt<2) Thread.sleep(250L*(attempt+1))
            }
        }
        throw lastError ?: IllegalStateException("Schedule request failed")
    }
}
