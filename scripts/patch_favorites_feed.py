#!/usr/bin/env python3
from pathlib import Path

P = Path("app/src/main/java/com/xsportsx/app/TeamFavorites.kt")
s = P.read_text()
old = '''    LaunchedEffect(selected){
        loading=true
        events=runCatching{SportsScheduleService.load()}.getOrDefault(emptyList())
        news=loadFavoriteNews(selected.take(6))
        loading=false
        if(active==null||active !in selected)active=selected.firstOrNull()
    }'''
new = '''    LaunchedEffect(selected){
        loading=true
        val snapshot=selected
        val data=runCatching{loadFavoriteFeed(snapshot)}.getOrDefault(FavoriteFeed(emptyList(),emptyList()))
        events=data.events
        news=data.news
        loading=false
        if(active==null||active !in snapshot)active=snapshot.firstOrNull()
    }'''
if old not in s:
    raise SystemExit("FavoritesCenter loading block not found")
s = s.replace(old, new, 1)
marker = '\nprivate suspend fun loadFavoriteNews(teams:List<FavoriteTeam>)'
pos = s.find(marker)
if pos < 0:
    raise SystemExit("old favorite news functions not found")
s = s[:pos] + r'''

data class FavoriteFeed(val events:List<SportsEvent>,val news:List<FavoriteNews>)

private suspend fun loadFavoriteFeed(teams:List<FavoriteTeam>):FavoriteFeed=withContext(Dispatchers.IO){
    val eventOut=ArrayList<SportsEvent>()
    val newsOut=ArrayList<FavoriteNews>()
    teams.take(12).forEach{team->
        val path=favoriteEspnPath(team) ?: return@forEach
        val teamId=resolveFavoriteTeamId(path,team) ?: return@forEach
        runCatching{eventOut += fetchFavoriteTeamSchedule(path,team,teamId)}
        runCatching{newsOut += fetchFavoriteTeamNews(path,team,teamId)}
    }
    FavoriteFeed(
        eventOut.distinctBy{it.id.ifBlank{it.title+it.startUtc}}.sortedWith(compareBy<SportsEvent>{!it.isLive}.thenBy{it.startUtc}),
        newsOut.distinctBy{it.url.ifBlank{it.headline}}.sortedByDescending{it.published}.take(24)
    )
}

private fun favoriteEspnPath(team:FavoriteTeam):String?=when(team.league){
    "NFL"->"football/nfl"
    "NBA"->"basketball/nba"
    "MLB"->"baseball/mlb"
    "NHL"->"hockey/nhl"
    else->null
}

private fun resolveFavoriteTeamId(path:String,team:FavoriteTeam):String?{
    val root=runCatching{JSONObject(favoriteHttp("https://site.api.espn.com/apis/site/v2/sports/$path/teams?limit=1000"))}.getOrNull()?:return null
    val teams=root.optJSONObject("sports")?.optJSONArray("teams")
        ?:root.optJSONArray("teams")
        ?:root.optJSONObject("league")?.optJSONArray("teams")
        ?:return null
    val wanted=team.name.lowercase();val abbr=team.abbr.lowercase()
    for(i in 0 until teams.length()){
        val wrapper=teams.optJSONObject(i)?:continue
        val t=wrapper.optJSONObject("team")?:wrapper
        val name=t.optString("displayName").ifBlank{t.optString("name")}.lowercase()
        val short=t.optString("shortDisplayName").lowercase()
        val code=t.optString("abbreviation").lowercase()
        if(name==wanted||short==wanted||code==abbr||name.contains(wanted)||wanted.contains(name))return t.optString("id").takeIf{it.isNotBlank()}
    }
    return null
}

private fun fetchFavoriteTeamSchedule(path:String,team:FavoriteTeam,teamId:String):List<SportsEvent>{
    val root=JSONObject(favoriteHttp("https://site.api.espn.com/apis/site/v2/sports/$path/teams/$teamId/schedule?limit=100"))
    val events=root.optJSONArray("events")?:return emptyList()
    val out=ArrayList<SportsEvent>()
    for(i in 0 until events.length()){
        val e=events.optJSONObject(i)?:continue
        val c=e.optJSONArray("competitions")?.optJSONObject(0)?:continue
        val competitors=c.optJSONArray("competitors")?:continue
        var home="";var away="";var homeLogo="";var awayLogo=""
        for(j in 0 until competitors.length()){
            val x=competitors.optJSONObject(j)?:continue
            val t=x.optJSONObject("team")?:continue
            val name=t.optString("displayName").ifBlank{t.optString("shortDisplayName")}
            val logo=t.optString("logo")
            if(x.optString("homeAway").equals("home",true)){home=name;homeLogo=logo}else{away=name;awayLogo=logo}
        }
        val st=c.optJSONObject("status")?:e.optJSONObject("status")?:JSONObject()
        val typ=st.optJSONObject("type")?:JSONObject()
        val state=typ.optString("state").ifBlank{st.optString("state")}
        val detail=typ.optString("shortDetail").ifBlank{typ.optString("detail")}.ifBlank{"Scheduled"}
        val title=e.optString("shortName").ifBlank{e.optString("name")}.ifBlank{"$away vs $home"}
        if(state.equals("post",true)||state.equals("final",true))continue
        out += SportsEvent(e.optString("id"),team.sport,team.league,title,e.optString("date"),detail,state,home,away,homeLogo,awayLogo,"",e.optString("image"),"https://www.espn.com/")
    }
    return out.filter{it.isLive||it.isUpcoming}
}

private fun fetchFavoriteTeamNews(path:String,team:FavoriteTeam,teamId:String):List<FavoriteNews>{
    val root=JSONObject(favoriteHttp("https://site.api.espn.com/apis/site/v2/sports/$path/teams/$teamId/news?limit=20"))
    val articles=root.optJSONArray("articles")?:return emptyList()
    val out=ArrayList<FavoriteNews>()
    for(i in 0 until articles.length()){
        val a=articles.optJSONObject(i)?:continue
        val headline=a.optString("headline").ifBlank{a.optString("title")}
        if(headline.isBlank())continue
        val links=a.optJSONObject("links")
        val web=links?.optString("web").orEmpty()
        out += FavoriteNews(team.abbr,headline,a.optString("description"),a.optString("published"),web)
    }
    return out
}

private fun favoriteHttp(target:String):String{
    val c=(URL(target).openConnection() as HttpURLConnection).apply{
        requestMethod="GET";connectTimeout=2500;readTimeout=5000;instanceFollowRedirects=true
        setRequestProperty("User-Agent","XSportsX/1.8 (Android)")
        setRequestProperty("Accept","application/json,text/plain,*/*")
    }
    return try{
        val code=c.responseCode
        if(code !in 200..299)error("Favorites HTTP $code")
        c.inputStream.bufferedReader(Charsets.UTF_8).use{it.readText()}
    }finally{c.disconnect()}
}
'''
P.write_text(s)
print(f"patched {P}")