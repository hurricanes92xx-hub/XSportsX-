package com.xsportsx.app

import android.util.LruCache
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedInputStream
import java.net.HttpURLConnection
import java.net.URL

data class PublicResolvedStream(val name:String,val group:String,val url:String,val iconUrl:String="",val sourceName:String="Public source",val latencyMs:Int=0)

class PublicSourceResolver {
 companion object {
  private const val CACHE_TTL_MS=10*60*1000L
  private const val MAX_PLAYLIST_BYTES=12_000_000
  private const val MAX_CANDIDATES=500
  private const val PER_SOURCE_CANDIDATES=180
  private const val MAX_HEALTH_CHECKS=240
  private const val HEALTH_CONCURRENCY=16
  private const val MAX_TARGETED_BYTES=12_000_000
  private const val TARGETED_CONCURRENCY=6
  private val REGISTRY_URLS=listOf(
   "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/android-app/docs/public-sources-registry.json",
   "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/main/docs/public-sources-registry.json",
   "https://cdn.jsdelivr.net/gh/hurricanes92xx-hub/XSportsX-@android-app/docs/public-sources-registry.json",
   "https://cdn.jsdelivr.net/gh/hurricanes92xx-hub/XSportsX-@main/docs/public-sources-registry.json")
  private val registryHosts=setOf("iptv-org.github.io","raw.githubusercontent.com","github.com","cdn.jsdelivr.net","dearbulut.github.io","i.mjh.nz")
  private val networkAliases=mapOf(
   "ESPN" to listOf("ESPN","ESPN2","ESPNU","ESPN Deportes","ESPN News","ESPN on ABC"),
   "FOX" to listOf("FOX","FOX Sports","Fox Sports 1","FS1","Fox Sports 2","FS2","FOX Deportes"),
   "CBS" to listOf("CBS","CBS Sports","CBS Sports Network","CBS Sports HQ","CBS Sports Golazo"),
   "NBC" to listOf("NBC","NBC Sports","NBC Sports Now","NBCSN","Peacock"),
   "ABC" to listOf("ABC","ESPN on ABC"),
   "TNT" to listOf("TNT","TNT Sports"),
   "NBA" to listOf("NBA TV","NBA"),
   "NFL" to listOf("NFL Network","NFL Channel","NFL"),
   "MLB" to listOf("MLB Network","MLB"),
   "NHL" to listOf("NHL Network","NHL"),
   "SEC" to listOf("SEC Network","SECN","SEC Network+"),
   "ACC" to listOf("ACC Network","ACCN","ACCNX","ACC Digital Network","ACCDN"),
   "BTN" to listOf("Big Ten Network","BTN"),
   "CW" to listOf("The CW","CW Sports"),
   "FANDUEL" to listOf("FanDuel TV","FanDuel Racing"),
   "DAZN" to listOf("DAZN","DAZN Combat"),
   "TSN" to listOf("TSN","TSN1","TSN2","TSN3","TSN4","TSN5"),
   "SPORTSNET" to listOf("Sportsnet","Sportsnet One","Sportsnet Ontario","Sportsnet Pacific","Sportsnet West","Sportsnet East")
  )
  private val sportsTerms=Regex("\\b(sport|sports|espn|fox sports|fs1|fs2|tnt|tbs|nba|mlb|nhl|nfl|ncaaf|ncaab|wnba|sec network|secn|acc network|accn|accdn|big ten|btn|pac 12|baseball|basketball|football|hockey|soccer|cbs sports|nbc sports|fubo sports|fanduel|sportsgrid|stadium|fifa\\+|real madrid tv|motorsport|f1|formula|racing|ufc|boxing|nascar|sportsnet|tsn|fifa|abc|cbs|nbc|fox|cw network|peacock|paramount|red bull|rugby|volleyball|lacrosse|wrestling|mavtv|dazn|dazn combat|l'equipe|teledeporte|rta sport|rtsh sport|trace sports stars|unbeaten|world of freesports|more than sports|fuel tv)\\b",RegexOption.IGNORE_CASE)
 }
 private val cache=LruCache<String,Pair<Long,List<PublicResolvedStream>>>(1)

 suspend fun load(force:Boolean=false):List<PublicResolvedStream>=withContext(Dispatchers.IO){
  val now=System.currentTimeMillis();val hit=cache.get("public")
  if(!force&&hit!=null&&now-hit.first<CACHE_TTL_MS)return@withContext hit.second
  val registry=fetchRegistry()?.let{runCatching{JSONObject(it)}.getOrNull()}?:return@withContext hit?.second.orEmpty()
  val sources=registry.optJSONArray("sources")?:JSONArray();val candidates=ArrayList<PublicResolvedStream>(MAX_CANDIDATES)
  for(i in 0 until sources.length()){
   if(candidates.size>=MAX_CANDIDATES)break;val s=sources.optJSONObject(i)?:continue
   if(!s.optBoolean("enabled",false)||!s.optBoolean("public",false))continue
   val playlist=s.optString("playlist").trim();if(!isAllowedRegistryUrl(playlist))continue
   val body=fetchText(playlist,MAX_PLAYLIST_BYTES,true)?:continue;val remain=MAX_CANDIDATES-candidates.size
   candidates+=parseM3u(body,s.optString("name").ifBlank{"Public source"},s.optString("allowlist"),minOf(PER_SOURCE_CANDIDATES,remain))
  }
  val unique=candidates.distinctBy{it.url}.take(MAX_CANDIDATES)
  val checked=coroutineScope{unique.take(MAX_HEALTH_CHECKS).chunked(HEALTH_CONCURRENCY).flatMap{b->b.map{async(Dispatchers.IO){health(it)}}.awaitAll().filterNotNull()}}
  val good=checked.map{it.url}.toSet();val result=(checked+unique.filterNot{it.url in good}).distinctBy{it.url}.take(MAX_CANDIDATES)
  cache.put("public",now to result);result
 }

 suspend fun searchTargeted(terms:List<String>):List<PublicResolvedStream>=withContext(Dispatchers.IO){
  val expanded=expandNetworkTerms(terms).map(::normalize).filter{it.length>=2}.distinct();if(expanded.isEmpty())return@withContext emptyList()
  val registry=fetchRegistry()?.let{runCatching{JSONObject(it)}.getOrNull()}?:return@withContext emptyList();val sources=registry.optJSONArray("sources")?:JSONArray();val configs=mutableListOf<Triple<String,String,String>>()
  for(i in 0 until sources.length()){val s=sources.optJSONObject(i)?:continue;if(s.optBoolean("enabled",false)&&s.optBoolean("public",false)){val p=s.optString("playlist").trim();if(isAllowedRegistryUrl(p))configs+=Triple(p,s.optString("name").ifBlank{"Public source"},s.optString("allowlist"))}}
  coroutineScope{configs.chunked(TARGETED_CONCURRENCY).flatMap{b->b.map{(p,n,a)->async(Dispatchers.IO){runCatching{val body=fetchText(p,MAX_TARGETED_BYTES,true)?:return@runCatching emptyList<PublicResolvedStream>();parseTargetedM3u(body,n,a,expanded)}.getOrDefault(emptyList())}}.awaitAll().flatten()}}.distinctBy{it.url}.sortedByDescending{targetedScore(it.name,it.group,expanded)}
 }

 private fun expandNetworkTerms(terms:List<String>):List<String>{val out=terms.toMutableList();for(t in terms){val n=normalize(t);networkAliases.entries.firstOrNull{e->normalize(e.key)==n||e.value.any{normalize(it)==n}}?.let{out+=it.value}};return out}
 private fun parseM3u(text:String,source:String,allow:String,max:Int):List<PublicResolvedStream>{val r=ArrayList<PublicResolvedStream>();var name="";var group="LIVE";var icon="";for(line in text.lineSequence()){val v=line.trim();when{v.startsWith("#EXTINF",true)->{name=v.substringAfterLast(',',"Unnamed").trim();group=attr(v,"group-title").ifBlank{"LIVE"};icon=attr(v,"tvg-logo")};v.isNotBlank()&&!v.startsWith("#")-> {if(name.isNotBlank()&&isAllowedStream(v)&&isSports(name,group)&&matchesAllowlist(name,group,allow))r+=PublicResolvedStream(name,group,v,icon,source);name="";group="LIVE";icon=""}};if(r.size>=max)break};return r}
 private fun parseTargetedM3u(text:String,source:String,allow:String,terms:List<String>):List<PublicResolvedStream>{val r=ArrayList<PublicResolvedStream>();var name="";var group="LIVE";var icon="";for(line in text.lineSequence()){val v=line.trim();when{v.startsWith("#EXTINF",true)->{name=v.substringAfterLast(',',"Unnamed").trim();group=attr(v,"group-title").ifBlank{"LIVE"};icon=attr(v,"tvg-logo")};v.isNotBlank()&&!v.startsWith("#")-> {val score=targetedScore(name,group,terms);if(name.isNotBlank()&&isAllowedStream(v)&&matchesAllowlist(name,group,allow)&&score>0)r+=PublicResolvedStream(name,group,v,icon,source,score);name="";group="LIVE";icon=""}}};return r}
 private fun matchesAllowlist(name:String,group:String,allow:String)=allow.isBlank()||allow.split('|').any{it.isNotBlank()&&(name.contains(it.trim(),true)||group.contains(it.trim(),true))}
 private fun targetedScore(name:String,group:String,terms:List<String>):Int{val h=normalize("$name $group");var best=0;for(t in terms){if(h==t)best=maxOf(best,100)else if(h.contains(t))best=maxOf(best,90)else{val tok=t.split(' ').filter{it.length>=2};val hits=tok.count{h.contains(it)};if(tok.isNotEmpty()&&hits==tok.size)best=maxOf(best,80)else if(hits>0)best=maxOf(best,55)}};return best}
 private suspend fun health(stream:PublicResolvedStream):PublicResolvedStream?=withContext(Dispatchers.IO){runCatching{val st=System.currentTimeMillis();val c=URL(stream.url).openConnection() as HttpURLConnection;c.requestMethod="GET";c.connectTimeout=3000;c.readTimeout=3500;c.instanceFollowRedirects=true;c.setRequestProperty("User-Agent","XSportsX-public-health/1.1");val code=c.responseCode;if(code !in 200..299){c.disconnect();return@runCatching null};val input=BufferedInputStream(c.inputStream);val b=ByteArray(4096);val count=input.read(b);input.close();c.disconnect();if(count<=0)return@runCatching null;stream.copy(latencyMs=(System.currentTimeMillis()-st).toInt())}.getOrNull()}
 private fun isSports(n:String,g:String)=sportsTerms.containsMatchIn("$n $g")
 private fun isAllowedRegistryUrl(t:String)=runCatching{val u=URL(t);u.protocol.equals("https",true)&&registryHosts.any{u.host.equals(it,true)||u.host.endsWith(".$it",true)}}.getOrDefault(false)
 private fun isAllowedStream(t:String)=runCatching{URL(t).protocol.equals("https",true)}.getOrDefault(false)
 private suspend fun fetchRegistry():String?{for(t in REGISTRY_URLS){fetchText(t,256_000,true)?.let{return it}};return null}
 private suspend fun fetchText(t:String,max:Int,registryOnly:Boolean)=withContext(Dispatchers.IO){runCatching{if(registryOnly&&!isAllowedRegistryUrl(t))return@runCatching null;val c=URL(t).openConnection() as HttpURLConnection;c.requestMethod="GET";c.connectTimeout=5000;c.readTimeout=10000;c.instanceFollowRedirects=true;c.setRequestProperty("User-Agent","XSportsX-public/1.1");if(c.responseCode !in 200..299){c.disconnect();return@runCatching null};val i=BufferedInputStream(c.inputStream);val o=StringBuilder();val b=ByteArray(8192);var total=0;while(true){val n=i.read(b);if(n<=0)break;total+=n;if(total>max)break;o.append(String(b,0,n,Charsets.UTF_8))};i.close();c.disconnect();o.toString()}.getOrNull()}
 private fun attr(line:String,key:String)=Regex("$key=\\\"([^\\\"]*)\\\"",RegexOption.IGNORE_CASE).find(line)?.groupValues?.getOrNull(1).orEmpty()
 private fun normalize(v:String)=v.lowercase().replace("’","'").replace(Regex("[^a-z0-9]+")," ").trim().replace(Regex("\\s+")," ")
}