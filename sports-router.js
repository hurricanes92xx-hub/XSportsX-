import http from "node:http";
import crypto from "node:crypto";
import { getUfcData } from "./ufc-data.js";

const PORT=Number(process.env.PORT||7099);
const BASE=process.env.BASE_URL||"https://xsportsx.onrender.com";
const VERSION="5.0.22";
const ADDON_ID="com.xsportsx.sports.epg.v520";
const PREFIX="v520";
const SECRET=process.env.XSPORTSX_CONFIG_SECRET||"xsportsx-v520-stable-config-key";
const KEY=crypto.createHash("sha256").update(SECRET).digest();

const LEAGUES={nfl:["NFL","football","nfl","🏈"],ncaaf:["NCAA Football","football","college-football","🏈"],nba:["NBA","basketball","nba","🏀"],nhl:["NHL","hockey","nhl","🏒"],mlb:["MLB","baseball","mlb","⚾"],soccer:["Soccer","soccer","eng.1","⚽"],ufc:["UFC","mma","ufc","🥊"]};
const NEWS_GROUPS={"ESPN":["espn","espn2","espnu","espn news","espnews","espn deportes","espn+","espn plus"],"ACC Network":["acc network","accn"],"SEC Network":["sec network","secn"],"Big Ten Network":["big ten network","btn"],"NFL Network":["nfl network","nfln"],"MLB Network":["mlb network","mlbn"],"NBA TV":["nba tv","nbatv"],"NHL Network":["nhl network","nhln"],"CBS Sports":["cbs sports network","cbs sports","cbssn"],"Fox Sports":["fox sports","fox sports 1","fox sports 2","fs1","fs2"],"Golf Channel":["golf channel"],"TNT Sports":["tnt sports","tnt"],"NBC Sports":["nbc sports"],"beIN Sports":["bein sports","beinsports"],"Sportsnet":["sportsnet"],"Tennis Channel":["tennis channel"]};
const NEWS_ALIASES=Object.values(NEWS_GROUPS).flat();
const LOGO_FALLBACKS={"ESPN":"https://cdn.simpleicons.org/espn","NFL Network":"https://cdn.simpleicons.org/nfl","MLB Network":"https://cdn.simpleicons.org/mlb","NBA TV":"https://cdn.simpleicons.org/nba","NHL Network":"https://cdn.simpleicons.org/nhl","CBS Sports":"https://cdn.simpleicons.org/cbs","Fox Sports":"https://cdn.simpleicons.org/fox","Tennis Channel":"https://cdn.simpleicons.org/tennis","Golf Channel":"https://cdn.simpleicons.org/golf","Sportsnet":"https://cdn.simpleicons.org/sportsnet"};
const cache=new Map(),eventCache=new Map(),xtreamCache=new Map(),inFlight=new Map(),sourceMatchCache=new Map();
const clean=v=>String(v??"").replace(/\s+/g," ").trim();
const norm=v=>clean(v).toLowerCase().replace(/[^a-z0-9]+/g," ").trim();
const slug=v=>norm(v).replace(/\s+/g,"-");
function json(res,body,status=200,maxAge=0){res.writeHead(status,{"content-type":"application/json; charset=utf-8","cache-control":maxAge?`public,max-age=${maxAge},stale-while-revalidate=60`:"no-store","access-control-allow-origin":"*","x-xsportsx-version":VERSION,"x-xsportsx-addon-id":ADDON_ID});res.end(JSON.stringify(body));}
function svg(res,label,accent="#fff"){const safe=String(label).replace(/[<>&\"]/g," ");const body=`<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360"><rect width="640" height="360" rx="24" fill="#0b0c10"/><text x="320" y="205" text-anchor="middle" fill="${accent}" font-family="Arial,Helvetica,sans-serif" font-size="64" font-weight="800">${safe}</text></svg>`;res.writeHead(200,{"content-type":"image/svg+xml; charset=utf-8","cache-control":"public,max-age=86400"});res.end(body);}
function encryptConfig(v){const iv=crypto.randomBytes(12),c=crypto.createCipheriv("aes-256-gcm",KEY,iv);const data=Buffer.concat([c.update(JSON.stringify(v),"utf8"),c.final()]);return Buffer.concat([iv,c.getAuthTag(),data]).toString("base64url");}
function decryptConfig(token){try{if(!token)return null;const raw=Buffer.from(token,"base64url");if(raw.length<29)return null;const d=crypto.createDecipheriv("aes-256-gcm",KEY,raw.subarray(0,12));d.setAuthTag(raw.subarray(12,28));const v=JSON.parse(Buffer.concat([d.update(raw.subarray(28)),d.final()]).toString("utf8"));return v?.server&&v?.username&&v?.password?{server:String(v.server).replace(/\/+$/,""),username:String(v.username),password:String(v.password)}:null;}catch{return null;}}
function configFrom(reqUrl){const u=new URL(reqUrl,"http://localhost"),parts=u.pathname.split("/").filter(Boolean),i=parts.indexOf(PREFIX);if(i>=0&&parts[i+1]&&!['manifest.json','configure','health'].includes(parts[i+1]))return decryptConfig(decodeURIComponent(parts[i+1]));return decryptConfig(u.searchParams.get("config"));}
async function getJson(url,timeout=6500){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),timeout);try{const r=await fetch(url,{signal:controller.signal,headers:{accept:"application/json","user-agent":`XSportsX/${VERSION}`}});if(!r.ok)throw new Error(`HTTP ${r.status}`);return await r.json();}finally{clearTimeout(timer);}}
function xtreamApi(c,action=""){const u=new URL(`${c.server}/player_api.php`);u.searchParams.set("username",c.username);u.searchParams.set("password",c.password);if(action)u.searchParams.set("action",action);return u;}
async function xtream(c,action=""){const key=`api:${c.server}|${c.username}|${action}`,hit=xtreamCache.get(key);if(hit&&Date.now()-hit.at<300000)return hit.value;if(inFlight.has(key))return inFlight.get(key);const job=getJson(xtreamApi(c,action).toString()).then(v=>{xtreamCache.set(key,{at:Date.now(),value:v});return v}).catch(()=>hit?.value||null).finally(()=>inFlight.delete(key));inFlight.set(key,job);return job;}
function newsGroupFor(name,category){const v=norm(`${name||""} ${category||""}`);for(const [group,aliases] of Object.entries(NEWS_GROUPS))if(aliases.some(a=>v.includes(norm(a))))return group;return null;}
function newsScore(name,category){const v=norm(`${name||""} ${category||""}`);let score=0;for(const a of NEWS_ALIASES){const x=norm(a);if(v===x||v.includes(x))score=Math.max(score,100);}if(/\b(sports?|sports news|sports network|live sports|college sports|national sports)\b/i.test(`${name||""} ${category||""}`))score=Math.max(score,75);return score;}
function newsLogo(group,channelPoster){return channelPoster||LOGO_FALLBACKS[group]||`${BASE}/${PREFIX}/assets/news/${slug(group)}.svg`;}
function team(t={}){return{id:String(t.id||""),name:t.displayName||t.name||"",short:t.abbreviation||"",logo:t.logo||t.logos?.[0]?.href||""};}
function eventMeta(ev,league){const [name,,,icon]=LEAGUES[league]||[league,"","","🏆"],c=ev?.competitions?.[0],teams=c?.competitors||[],h=teams.find(x=>x.homeAway==="home")?.team||teams[0]?.team||{},a=teams.find(x=>x.homeAway==="away")?.team||teams[1]?.team||{};if(league!=="ufc"&&!h?.displayName&&!a?.displayName)return null;const state=c?.status?.type?.state||ev?.status?.type?.state||"pre",detail=c?.status?.type?.shortDetail||c?.status?.type?.detail||"Scheduled",start=ev.date||c?.date||"",id=`sport:${ev.id}`,eventName=league==="ufc"?(ev.name||ev.shortName||c?.name||"UFC Event"):`${a.displayName||"TBD"} vs ${h.displayName||"TBD"}`,poster=league==="ufc"?`${BASE}/${PREFIX}/assets/ufc.svg`:h.logo||h.logos?.[0]?.href||a.logo||undefined,meta={id,type:"channel",name:eventName,poster,background:poster,description:`${icon} ${name}\n${detail}\n${start}`,releaseInfo:start,genres:["Sports",name,state==="in"?"LIVE":"Scheduled"],sportSource:league,eventSport:league,league,eventId:String(ev.id),event:{id:String(ev.id),league,start,state,home:team(h),away:team(a),broadcast:(c?.broadcasts||[]).flatMap(x=>x.names||[])}};eventCache.set(id,meta);return meta;}
function leagueUrl(id){const [,sport,espn]=LEAGUES[id];return `https://site.api.espn.com/apis/site/v2/sports/${sport}/${espn}/scoreboard?limit=100`;}
async function leagueCatalog(id){const key=`league:${id}`,hit=cache.get(key);if(hit&&Date.now()-hit.at<60000)return hit.value;if(inFlight.has(key))return inFlight.get(key);const job=getJson(leagueUrl(id)).then(d=>{const metas=(d.events||[]).map(e=>eventMeta(e,id)).filter(Boolean).sort((a,b)=>new Date(a.releaseInfo||0)-new Date(b.releaseInfo||0));cache.set(key,{at:Date.now(),value:metas});return metas;}).catch(()=>hit?.value||[]).finally(()=>inFlight.delete(key));inFlight.set(key,job);return job;}
async function allSports(){const key="all:sports",hit=cache.get(key);if(hit&&Date.now()-hit.at<30000)return hit.value;if(inFlight.has(key))return inFlight.get(key);const job=Promise.all(Object.keys(LEAGUES).map(leagueCatalog)).then(x=>x.flat()).finally(()=>inFlight.delete(key));inFlight.set(key,job);const value=await job;cache.set(key,{at:Date.now(),value});return value;}
async function xtreamData(c){
if(!c)return{metas:[],news:[],newsGroups:[],categories:[]};
const key=`data:${c.server}|${c.username}`;
const hit=xtreamCache.get(key),now=Date.now();
if(hit&&now-hit.at<300000)return hit.value;
if(inFlight.has(key))return inFlight.get(key);
const job=(async()=>{
  const [cats,streams]=await Promise.all([
    xtream(c,"get_live_categories").catch(()=>null),
    xtream(c,"get_live_streams").catch(()=>null)
  ]);
  if(!Array.isArray(streams)||!streams.length){
    if(hit?.value)return hit.value;
    return {metas:[],news:[],newsGroups:[],categories:Array.isArray(cats)?cats.map(x=>x.category_name||"Live TV"):[]};
  }
  const cm=new Map((Array.isArray(cats)?cats:[]).map(x=>[String(x.category_id),x.category_name||"Live TV"]));
  const metas=streams.map(s=>{
    const cat=cm.get(String(s.category_id))||"Live TV";
    const ext=String(s.container_extension||"ts").replace(/[^a-z0-9]/gi,"")||"ts";
    return {id:`xtream:${s.stream_id}`,type:"channel",name:s.name||`Channel ${s.stream_id}`,poster:s.stream_icon||undefined,background:s.stream_icon||undefined,description:`📺 ${cat}`,genres:["IPTV","Live TV",cat],behaviorHints:{isLive:true},xtream:{streamUrl:`${c.server}/live/${encodeURIComponent(c.username)}/${encodeURIComponent(c.password)}/${encodeURIComponent(s.stream_id)}.${ext}`,category:cat}};
  });
  const scored=metas.map((m,i)=>({meta:m,source:streams[i],category:cm.get(String(streams[i]?.category_id))||"Live TV",score:newsScore(streams[i]?.name||m.name,cm.get(String(streams[i]?.category_id))||"Live TV")}));
  const news=scored.filter(x=>x.score>=70).map(x=>x.meta);
  const newsGroups=Object.entries(NEWS_GROUPS).map(([group])=>{
    const channels=scored.filter(x=>newsGroupFor(x.source?.name,x.category)===group);
    if(!channels.length)return null;
    return {id:`news:${newsSlug(group)}`,type:"channel",name:group,poster:newsLogo(group),background:newsLogo(group),description:`${channels.length} ${group} channel${channels.length===1?"":"s"} from your Xtream provider`,genres:["Sports News",group],behaviorHints:{isLive:true},newsGroup:group};
  }).filter(Boolean);
  const value={metas,news,newsGroups,categories:[...cm.values()]};
  xtreamCache.set(key,{at:Date.now(),value});
  return value;
})().catch(()=>hit?.value||{metas:[],news:[],newsGroups:[],categories:[]}).finally(()=>inFlight.delete(key));
inFlight.set(key,job);
return job;
}
function matchEventChannel(ch,e){
const text=norm(`${ch.name||''} ${ch.xtream?.category||''}`),a=e?.away||{},h=e?.home||{};
const aa=teamTerms(a),hh=teamTerms(h);let as=0,hs=0;
for(const x of aa)if(x&&text.includes(norm(x)))as=Math.max(as,x.length>=5?55:35);
for(const x of hh)if(x&&text.includes(norm(x)))hs=Math.max(hs,x.length>=5?55:35);
for(const b of e?.broadcast||[])if(norm(b)&&text.includes(norm(b)))return 100;
if(as>=55&&hs>=55)return 100;
if(as>=35&&hs>=35)return 80;
if(as>=55||hs>=55)return 65;
if(as>=35||hs>=35)return 45;
return 0;
}
async function streamsForEvent(c,meta){
if(!c||!meta?.event)return[];
const cacheKey=`match:${c.server}|${c.username}|${meta.id}`,hit=sourceMatchCache.get(cacheKey);
if(hit&&Date.now()-hit.at<60000)return hit.value;
const d=await xtreamData(c);let value=[];
if(meta.event.league==='ufc'){
  value=d.metas.filter(m=>/\b(ufc|ultimate fighting championship|fight pass|ufc fight|ufc network|paramount plus|paramount\+|cbs sports)\b/i.test(`${m.name} ${m.xtream?.category||''}`)).slice(0,20).map(m=>({name:`▶ ${m.name}`,url:m.xtream.streamUrl,title:m.name,description:m.xtream.category}));
}else{
  const e={away:meta.event.away,home:meta.event.home,broadcast:meta.event.broadcast||[]};
  value=d.metas.map(m=>({m,score:matchEventChannel(m,e)})).filter(x=>x.score>0).sort((a,b)=>b.score-a.score).slice(0,12).map(x=>({name:`▶ ${x.m.name}`,url:x.m.xtream.streamUrl,title:x.m.name,description:`${x.m.xtream.category} • event match ${x.score}%`,score:x.score}));
}
sourceMatchCache.set(cacheKey,{at:Date.now(),value});return value;
}
async function ufcCatalog(){
  try {
    const events=await getUfcData();
    const metas=events.map((e,i)=>({id:`sport:ufc-${e.id||i}`,type:"channel",name:e.name||"UFC Event",poster:`${BASE}${PREFIX}/assets/ufc.svg`,background:`${BASE}${PREFIX}/assets/ufc.svg`,description:`🥊 UFC\n${e.date||"Upcoming event"}\n${e.venue||""}`,releaseInfo:e.date||new Date().toISOString(),genres:["Sports","UFC","MMA"],sportSource:"ufc",eventSport:"ufc",league:"ufc",eventId:String(e.id||i),event:{id:String(e.id||i),league:"ufc",start:e.date||"",state:"pre",home:{name:"UFC",short:"UFC"},away:{name:e.name||"UFC Event",short:"UFC"}}}));
    if(metas.length)return metas.slice(0,50);
  } catch {}
  return [{id:"sport:ufc-command-center",type:"channel",name:"UFC Events & PPV",poster:`${BASE}${PREFIX}/assets/ufc.svg`,background:`${BASE}${PREFIX}/assets/ufc.svg`,description:"🥊 UFC Fight Night • PPV • UFC-related events",releaseInfo:new Date().toISOString(),genres:["Sports","UFC","MMA"],sportSource:"ufc",eventSport:"ufc",league:"ufc",eventId:"ufc-command-center",event:{id:"ufc-command-center",league:"ufc",start:"",state:"pre",home:{name:"UFC",short:"UFC"},away:{name:"UFC Events",short:"UFC"}}}];
}
async function resolveEventMeta(id){
const cached=await resolveEventMeta(id);
if(cached)return cached;
const raw=String(id||"").replace(/^sport:/,"");
for(const league of Object.keys(LEAGUES)){
  try{
    const rows=await leagueCatalog(league);
    const found=rows.find(m=>String(m.eventId)===raw||String(m.event?.id)===raw||String(m.id)===id);
    if(found)return found;
  }catch{}
}
return null;
}
function manifest(){const catalogs=[["sports-command-center","🏆 XSPORTSX • SPORTS COMMAND CENTER"],["live-now","🔴 LIVE NOW"],["starting-soon","⏰ STARTING SOON"],["sports-news-v2","📰 SPORTS NEWS NETWORKS"],["nfl","🏈 NFL"],["ncaaf","🏈 NCAA FOOTBALL"],["nba","🏀 NBA"],["nhl","🏒 NHL"],["mlb","⚾ MLB"],["ufc-v2","🥊 UFC COMMAND CENTER"],["soccer","⚽ SOCCER"],["iptv-live","📡 MY IPTV • LIVE TV"]];return{id:ADDON_ID,version:VERSION,name:"XSportsX Sports Command Center",description:"Fast sports EPG with authorized Xtream live TV, sports news and UFC events.",config:[{key:"server",type:"text",title:"Xtream Server URL"},{key:"username",type:"text",title:"Xtream Username"},{key:"password",type:"password",title:"Xtream Password"}],behaviorHints:{configurable:true,configurationRequired:false,configurationURL:`${BASE}/${PREFIX}/configure`},resources:[{name:"catalog",types:["channel"]},{name:"meta",types:["channel"],idPrefixes:["sport:","xtream:","news:"]},{name:"stream",types:["channel"],idPrefixes:["sport:","xtream:","news:"]}],types:["channel"],catalogs:catalogs.map(([id,name])=>({type:"channel",id,name,showInHome:true}))};}
function configurePage(){return `<!doctype html><html><head><meta name="viewport" content="width=device-width"><title>XSportsX</title></head><body style="margin:0;background:#08090c;color:#fff;font:16px system-ui;display:grid;place-items:center;min-height:100vh"><main style="width:min(520px,92vw);background:#12151b;padding:28px;border-radius:18px"><h1>🏆 XSportsX 5.0.22</h1><p>Enter your authorized Xtream credentials.</p><form method="post" action="${PREFIX}/configure"><label>Server URL</label><input name="server" required style="width:100%;box-sizing:border-box;padding:13px"><label>Username</label><input name="username" required style="width:100%;box-sizing:border-box;padding:13px"><label>Password</label><input name="password" type="password" required style="width:100%;box-sizing:border-box;padding:13px"><button style="width:100%;padding:14px;margin-top:20px">GENERATE NUVIO MANIFEST</button></form></main></body></html>`;}
function readyPage(url){return `<!doctype html><html><body style="background:#08090c;color:#fff;font:16px system-ui;padding:30px"><h1>✅ XSportsX 5.0.22 Ready</h1><p>Copy this manifest into Nuvio.</p><input style="width:100%;padding:14px" readonly value="${url.replace(/&/g,"&amp;").replace(/"/g,"&quot;")}"><p><a href="${url}">Open manifest</a></p></body></html>`;}

const server=http.createServer(async(req,res)=>{try{const u=new URL(req.url||"/","http://localhost"),path=u.pathname,c=configFrom(req.url||"/");if(path.endsWith("/assets/ufc.svg"))return svg(res,"UFC");if(path.includes("/assets/news/")&&path.endsWith(".svg"))return svg(res,path.split("/assets/news/")[1].slice(0,-4).replace(/-/g," ").replace(/\b\w/g,x=>x.toUpperCase()));if(path==="/manifest.json"||path===`/${PREFIX}/manifest.json`)return json(res,manifest(),200,0);if(path==="/health"||path===`/${PREFIX}/health`)return json(res,{ok:true,version:VERSION,addonId:ADDON_ID,nuvioCompatible:true});if(path==="/configure"||path===`/${PREFIX}/configure`){if(req.method==="GET"){res.writeHead(200,{"content-type":"text/html; charset=utf-8","cache-control":"no-store"});return res.end(configurePage());}if(req.method==="POST"){let body="";for await(const chunk of req)body+=chunk;const f=new URLSearchParams(body),cfg={server:clean(f.get("server")).replace(/\/+$/,""),username:clean(f.get("username")),password:String(f.get("password")||"")};if(!/^https?:\/\//i.test(cfg.server)||!cfg.username||!cfg.password){res.writeHead(400);return res.end("Missing or invalid credentials");}const token=encryptConfig(cfg),url=`${BASE}/${PREFIX}/${token}/manifest.json`;res.writeHead(200,{"content-type":"text/html; charset=utf-8","cache-control":"no-store"});return res.end(readyPage(url));}}if(path.includes("/catalog/channel/sports-news-v2.json")||path.includes("/catalog/channel/sports-news.json")){if(!c)return json(res,{metas:[]});return json(res,{metas:(await xtreamData(c)).newsGroups},200,30);}if(path.includes("/catalog/channel/iptv-live.json")){if(!c)return json(res,{metas:[]});return json(res,{metas:(await xtreamData(c)).metas},200,30);}if(path.includes("/catalog/channel/")){const id=path.split("/catalog/channel/")[1].replace(/\.json$/ ,"");if(id==="sports-command-center"){const ms=await allSports();return json(res,{metas:ms.slice(0,50)},200,15);}if(id==="live-now"){const ms=await allSports();return json(res,{metas:ms.filter(m=>m.event?.state==="in").slice(0,50)},200,15);}if(id==="starting-soon"){const ms=await allSports(),cut=Date.now()+86400000;return json(res,{metas:ms.filter(m=>m.event?.state==="pre"&&new Date(m.releaseInfo).getTime()<=cut).slice(0,50)},200,15);}if(id==="ufc"||id==="ufc-v2"){const events=await leagueCatalog("ufc");const metas=events.length?events.slice(0,100):[{id:"sport:ufc-hub",type:"channel",name:"UFC — Events & Fight Nights",poster:`${BASE}/${PREFIX}/assets/ufc.svg`,background:`${BASE}/${PREFIX}/assets/ufc.svg`,description:"UFC Fight Nights, PPV and related UFC events",genres:["Sports","UFC"],eventSport:"ufc",league:"ufc",event:{league:"ufc",state:"pre"}}];return json(res,{metas},200,30);}if(id==="ufc"){return json(res,{metas:await ufcCatalog(c)},200,30);}if(id==="ufc"){return json(res,{metas:await ufcCatalog(c)},200,30);}if(id==="ufc"){return json(res,{metas:await ufcCatalog(c)},200,30);}if(id==="ufc"){return json(res,{metas:await ufcCatalog(c)},200,30);}if(id==="ufc"){return json(res,{metas:await ufcCatalog(c)},200,30);}if(id==="ufc"){return json(res,{metas:await ufcCatalog(c)},200,30);}if(id==="ufc"){return json(res,{metas:await ufcCatalog(c)},200,30);}if(id==="ufc"){return json(res,{metas:await ufcCatalog(c)},200,30);}if(id==="ufc"){return json(res,{metas:await ufcCatalog(c)},200,30);}if(id==="ufc"){return json(res,{metas:await ufcCatalog(c)},200,30);}if(LEAGUES[id])return json(res,{metas:await leagueCatalog(id)},200,15);return json(res,{metas:[]});}if(path.includes("/meta/channel/")){const id=decodeURIComponent(path.split("/meta/channel/")[1].replace(/\.json$/ ,""));if(id.startsWith("news:")){if(!c)return json(res,{meta:null},401);const d=await xtreamData(c),m=d.newsGroups.find(x=>x.id===id)||null;return json(res,{meta:m},m?200:404);}if(id==="sport:ufc-hub")return json(res,{meta:{id:"sport:ufc-hub",type:"channel",name:"UFC — Events & Fight Nights",poster:`${BASE}/${PREFIX}/assets/ufc.svg`,background:`${BASE}/${PREFIX}/assets/ufc.svg`,description:"UFC Fight Nights, PPV and related UFC events",genres:["Sports","UFC"],eventSport:"ufc"}});if(id.startsWith("xtream:")){if(!c)return json(res,{meta:null},401);const m=(await xtreamData(c)).metas.find(x=>x.id===id)||null;return json(res,{meta:m},m?200:404);}if(id.startsWith("sport:")){const all=await allSports(),m=all.find(x=>x.id===id)||null;return json(res,{meta:m},m?200:404);}return json(res,{meta:null},404);}if(path.includes("/stream/channel/")){const id=decodeURIComponent(path.split("/stream/channel/")[1].replace(/\.json$/ ,""));if(id.startsWith("news:")){if(!c)return json(res,{streams:[]},401);const d=await xtreamData(c),g=d.newsGroups.find(x=>x.id===id),rows=g?.newsGroup==="__ALL_SPORTS_NEWS__"?d.news:d.metas.filter(m=>newsGroupFor(m.name,m.xtream?.category)===g?.newsGroup);return json(res,{streams:rows.map(m=>({name:`▶ ${m.name}`,url:m.xtream.streamUrl,title:m.name,description:m.xtream.category}))});}if(id.startsWith("xtream:")){if(!c)return json(res,{streams:[]},401);const m=(await xtreamData(c)).metas.find(x=>x.id===id);return json(res,{streams:m?.xtream?.streamUrl?[{name:`▶ ${m.name}`,url:m.xtream.streamUrl,title:m.name}]:[]});}if(id==="sport:ufc-hub"){if(!c)return json(res,{streams:[]},401);const d=await xtreamData(c),rows=d.metas.filter(m=>/\b(ufc|ultimate fighting championship|fight pass|ufc fight|paramount plus|paramount\+|cbs sports)\b/i.test(`${m.name} ${m.xtream?.category||""}`));return json(res,{streams:rows.slice(0,20).map(m=>({name:`▶ ${m.name}`,url:m.xtream.streamUrl,title:m.name,description:m.xtream.category}))});}let m=eventCache.get(id);if(!m&&id.startsWith("sport:")){const all=await allSports();m=all.find(x=>x.id===id);if(m)eventCache.set(id,m);}return json(res,{streams:await streamsForEvent(c,m)});}return json(res,{error:"Not found"},404);}catch(e){return json(res,{error:String(e?.message||e)},502);}});
server.keepAliveTimeout=120000;server.headersTimeout=125000;server.requestTimeout=120000;server.listen(PORT,"0.0.0.0",()=>console.log(`XSportsX ${VERSION} listening on ${PORT}`));
