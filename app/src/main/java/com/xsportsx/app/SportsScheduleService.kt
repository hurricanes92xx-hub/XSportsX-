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
    // Keep every competition on its own stable league key. In particular,
    // NCAA FB and NCAA BB must never share the generic "NCAA" key or their
    // schedules will be mixed together in the home/top-sports UI.
    private val leagues=listOf(
        ScheduleLeague("Football","NFL","football/nfl","https://www.nfl.com/schedules/"),
        ScheduleLeague("College Football","NCAA FB","football/college-football","https://www.ncaa.com/scoreboard/football/fbs"),
        ScheduleLeague("Basketball","NBA","basketball/nba","https://www.nba.com/schedule"),
        ScheduleLeague("Basketball","WNBA","basketball/wnba","https://www.wnba.com/schedule"),
        ScheduleLeague("College Basketball","NCAA BB","basketball/mens-college-basketball","https://www.ncaa.com/scoreboard/basketball-men/d1"),
        ScheduleLeague("Baseball","MLB","baseball/mlb","https://www.mlb.com/schedule"),
        ScheduleLeague("Hockey","NHL","hockey/nhl","https://www.nhl.com/schedule"),
        ScheduleLeague("Soccer","MLS","soccer/usa.1","https://www.mlssoccer.com/schedule"),
        ScheduleLeague("Soccer","EPL","soccer/eng.1","https://www.premierleague.com/fixtures"),
        ScheduleLeague("Soccer","LaLiga","soccer/esp.1","https://www.laliga.com/en-GB/laliga-easports/results"),
        ScheduleLeague("Soccer","Bundesliga","soccer/ger.1","https://www.bundesliga.com/en/bundesliga/matchday"),
        ScheduleLeague("Soccer","Serie A","soccer/ita.1","https://www.legaseriea.it/en"),
        ScheduleLeague("Soccer","Ligue 1","soccer/fra.1","https://www.ligue1.com/"),
        ScheduleLeague("Soccer","UCL","soccer/uefa.champions","https://www.uefa.com/uefachampionsleague/fixtures-results/"),
        ScheduleLeague("Soccer","UEL","soccer/uefa.europa","https://www.uefa.com/uefaeuropaleague/fixtures-results/"),
        ScheduleLeague("Soccer","NWSL","soccer/usa.nwsl","https://www.nwslsoccer.com/schedule"),
        ScheduleLeague("Racing","F1","racing/f1","https://www.formula1.com/en/racing/2026"),
        ScheduleLeague("MMA","UFC","mma/ufc","https://www.ufc.com/events"),
        ScheduleLeague("Boxing","BOXING","boxing/boxing","https://wbcboxing.com/en/eventos/list/")
    )

    suspend fun load():List<SportsEvent> = withContext(Dispatchers.IO) {
        val today=LocalDate.now(ZoneId.systemDefault())
        val end=today.plusDays(30)
        val dates="${today.format(DateTimeFormatter.BASIC_ISO_DATE)}-${end.format(DateTimeFormatter.BASIC_ISO_DATE)}"
        val limiter=Semaphore(8)

        val results=withTimeout(28_000L) {
            coroutineScope {
                leagues.map { league ->
                    async {
                        limiter.withPermit { fetchLeagueWithFallbacks(league,dates,today,end) }
                    }
                }.awaitAll()
            }
        }

        results.flatten()
            .distinctBy { it.id.ifBlank { it.title+it.startUtc+it.league } }
            .filter { it.isLive || it.isUpcoming }
            .sortedWith(compareBy<SportsEvent>{ !it.isLive }.thenBy { it.startUtc })
    }

    private suspend fun fetchLeagueWithFallbacks(
        league:ScheduleLeague,
        dates:String,
        from:LocalDate,
        to:LocalDate
    ):List<SportsEvent> {
        val sources=mutableListOf<List<SportsEvent>>()
        runCatching { sources += fetchEspn(league,dates) }
        if(sources.lastOrNull().isNullOrEmpty()) runCatching { sources += fetchEspnV3(league,dates) }

        when(league.league){
            "MLB" -> runCatching { sources += fetchMlbOfficial(from,to) }
            "NHL" -> runCatching { sources += fetchNhlOfficial(from,to) }
            "F1" -> runCatching { sources += fetchF1Fallback(from,to) }
        }

        return sources.flatten()
            .filter { it.league.equals(league.league,true) }
            .map { it.copy(sourceUrl = it.sourceUrl.ifBlank { league.officialUrl }) }
            .distinctBy { canonicalKey(it) }
    }

    private fun canonicalKey(e:SportsEvent):String =
        listOf(e.league,normalize(e.home),normalize(e.away),e.startUtc.take(10)).joinToString("|")

    private fun normalize(v:String):String = v.lowercase().replace("fc"," ").replace("  "," ").trim()

    private fun fetchEspn(league:ScheduleLeague,dates:String):List<SportsEvent>{
        val url="https://site.api.espn.com/apis/site/v2/sports/${league.path}/scoreboard?dates=$dates&limit=1000"
        return parseEspn(JSONObject(http(url)),league)
    }

    private fun fetchEspnV3(league:ScheduleLeague,dates:String):List<SportsEvent>{
        val url="https://site.api.espn.com/apis/site/v3/sports/${league.path}/scoreboard?dates=$dates&limit=1000"
        return parseEspn(JSONObject(http(url)),league)
    }

    private fun parseEspn(root:JSONObject,league:ScheduleLeague):List<SportsEvent>{
        val events=root.optJSONArray("events") ?: root.optJSONObject("content")?.optJSONArray("events") ?: return emptyList()
        val out=ArrayList<SportsEvent>(events.length())
        for(i in 0 until events.length()){
            val e=events.optJSONObject(i) ?: continue
            val competition=e.optJSONArray("competitions")?.optJSONObject(0) ?: continue
            val competitors=competition.optJSONArray("competitors") ?: continue
            var home="";var away="";var homeLogo="";var awayLogo=""
            for(j in 0 until competitors.length()){
                val c=competitors.optJSONObject(j) ?: continue
                val team=c.optJSONObject("team")
                val athlete=c.optJSONObject("athlete")
                val name=team?.optString("displayName")?.ifBlank { team.optString("shortDisplayName") }
                    ?: athlete?.optString("displayName")?.ifBlank { athlete.optString("shortName") }
                    ?: c.optString("displayName")
                val logo=team?.optString("logo")?.ifBlank { team.optJSONArray("logos")?.optJSONObject(0)?.optString("href") ?: "" } ?: ""
                if(c.optString("homeAway").equals("home",true)){home=name;homeLogo=logo}else{away=name;awayLogo=logo}
            }
            val rawName=e.optString("name").ifBlank { e.optString("shortName") }
            val status=competition.optJSONObject("status") ?: e.optJSONObject("status") ?: JSONObject()
            val type=status.optJSONObject("type") ?: JSONObject()
            val state=type.optString("state").ifBlank { status.optString("state") }
            val detail=type.optString("shortDetail").ifBlank { type.optString("detail") }.ifBlank { status.optString("displayClock") }
            val broadcasts=competition.optJSONArray("broadcasts")
            val broadcast=buildString {
                if(broadcasts!=null) for(j in 0 until broadcasts.length()){
                    val names=broadcasts.optJSONObject(j)?.optJSONArray("names")
                    if(names!=null) for(k in 0 until names.length()){if(isNotEmpty())append(", ");append(names.optString(k))}
                }
            }
            val start=e.optString("date").ifBlank { competition.optString("startDate") }
            val title=rawName.ifBlank { listOf(home,away).filter { it.isNotBlank() }.joinToString(" vs ") }
            out += SportsEvent(e.optString("id"),league.sport,league.league,title,start,detail,state,home,away,homeLogo,awayLogo,broadcast,e.optString("image"),league.officialUrl)
        }
        return out
    }

    private fun fetchMlbOfficial(from:LocalDate,to:LocalDate):List<SportsEvent>{
        val url="https://statsapi.mlb.com/api/v1/schedule?sportId=1&startDate=$from&endDate=$to&hydrate=team,venue"
        val root=JSONObject(http(url));val days=root.optJSONArray("dates") ?: return emptyList();val out=ArrayList<SportsEvent>()
        for(i in 0 until days.length()){
            val games=days.optJSONObject(i)?.optJSONArray("games") ?: continue
            for(j in 0 until games.length()){
                val g=games.optJSONObject(j) ?: continue;val teams=g.optJSONObject("teams") ?: continue
                val h=teams.optJSONObject("home")?.optJSONObject("team");val a=teams.optJSONObject("away")?.optJSONObject("team")
                val state=g.optJSONObject("status")?.optString("abstractGameState").orEmpty().lowercase()
                val detail=g.optJSONObject("status")?.optString("detailedState").orEmpty()
                val home=h?.optString("name").orEmpty();val away=a?.optString("name").orEmpty()
                out += SportsEvent("mlb-${g.optInt("gamePk")}","Baseball","MLB","$away vs $home",g.optString("gameDate"),detail,if(state=="live")"in" else if(state=="preview")"pre" else state,home,away,"","","", "https://www.mlb.com/schedule","https://www.mlb.com/schedule")
            }
        }
        return out
    }

    private fun fetchNhlOfficial(from:LocalDate,to:LocalDate):List<SportsEvent>{
        val out=ArrayList<SportsEvent>();var d=from
        while(!d.isAfter(to)){
            runCatching{
                val root=JSONObject(http("https://api-web.nhle.com/v1/schedule/$d"));val dates=root.optJSONArray("gameWeek") ?: return@runCatching
                for(i in 0 until dates.length()){
                    val day=dates.optJSONObject(i) ?: continue;val games=day.optJSONArray("games") ?: continue
                    for(j in 0 until games.length()){
                        val g=games.optJSONObject(j) ?: continue;val h=g.optJSONObject("homeTeam");val a=g.optJSONObject("awayTeam")
                        val state=g.optString("gameState").lowercase()
                        val mapped=when(state){"live","critical"->"in";"future","preview"->"pre";else->"post"}
                        if(mapped=="post")continue
                        out += SportsEvent("nhl-${g.optInt("id")}","Hockey","NHL","${a?.optString("place","Away")} ${a?.optString("commonName","")} vs ${h?.optString("place","Home")} ${h?.optString("commonName","")}",g.optString("startTimeUTC"),g.optString("gameScheduleState"),mapped,h?.optString("place","").orEmpty(),a?.optString("place","").orEmpty(),h?.optString("logo","").orEmpty(),a?.optString("logo","").orEmpty(),"","https://www.nhl.com/schedule")
                    }
                }
            }
            d=d.plusDays(1)
        }
        return out
    }

    private fun fetchF1Fallback(from:LocalDate,to:LocalDate):List<SportsEvent>{
        val root=JSONObject(http("https://api.jolpi.ca/ergast/f1/${from.year}.json"));val races=root.optJSONObject("MRData")?.optJSONObject("RaceTable")?.optJSONArray("Races") ?: return emptyList();val out=ArrayList<SportsEvent>()
        for(i in 0 until races.length()){
            val r=races.optJSONObject(i) ?: continue;val date=r.optString("date");if(date.isBlank())continue
            val local=runCatching{LocalDate.parse(date)}.getOrNull() ?: continue;if(local.isBefore(from)||local.isAfter(to))continue
            val circuit=r.optJSONObject("Circuit")?.optString("circuitName").orEmpty();val name=r.optString("raceName")
            out += SportsEvent("f1-${r.optString("round")}","Racing","F1",name,"${date}T${r.optString("time","12:00:00Z")}","Scheduled","pre",circuit,"","","","","https://www.formula1.com/en/racing/${from.year}","https://www.formula1.com/en/racing/${from.year}")
        }
        return out
    }

    private fun http(target:String):String{
        val c=(URL(target).openConnection() as HttpURLConnection).apply{
            requestMethod="GET";connectTimeout=2200;readTimeout=4500;instanceFollowRedirects=true
            setRequestProperty("User-Agent","XSportsX/1.5 (Android)")
            setRequestProperty("Accept","application/json,text/plain,*/*")
        }
        return try{val code=c.responseCode;if(code !in 200..299)error("Schedule HTTP $code");c.inputStream.bufferedReader(Charsets.UTF_8).use{it.readText()}}finally{c.disconnect()}
    }
}
