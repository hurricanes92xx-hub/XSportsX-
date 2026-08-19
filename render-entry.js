import http from "node:http";
import { spawn } from "node:child_process";

const PUBLIC_PORT = Number(process.env.PORT || 7000);
const GATEWAY_PORT = Number(process.env.XSPORTSX_GATEWAY_PORT || 7002);
const BACKEND_PORT = Number(process.env.XSPORTSX_BACKEND_PORT || 7001);
const BASE = process.env.BASE_URL || "https://xsportsx.onrender.com";
const VERSION = "3.9.7";
const ESPN = "https://a.espncdn.com/i/teamlogos/leagues/500/";
const GENERIC = "https://commons.wikimedia.org/wiki/Special:Redirect/file/ESPN_logo.png";
const UFC = "https://upload.wikimedia.org/wikipedia/commons/4/4f/UFC_Logo.png";
const NCAA = "https://commons.wikimedia.org/wiki/Special:Redirect/file/NCAA_Football_wordmark_color.svg?width=960";
const ASSETS = {
  nfl:`${ESPN}nfl.png`, nba:`${ESPN}nba.png`, nhl:`${ESPN}nhl.png`, mlb:`${ESPN}mlb.png`,
  ncaaf:NCAA, ncaab:`${ESPN}ncaab.png`, wnba:`${ESPN}wnba.png`, mls:`${ESPN}mls.png`,
  "premier-league":`${ESPN}eng.1.png`, "la-liga":`${ESPN}esp.1.png`, f1:`${ESPN}f1.png`,
  motogp:`${ESPN}motogp.png`, ufc:UFC, boxing:GENERIC, atp:`${ESPN}atp.png`,
  wta:`${ESPN}wta.png`, pga:`${ESPN}pga.png`, rugby:GENERIC, cricket:GENERIC, pdc:GENERIC, afl:GENERIC
};
const ALIASES = {nfl:"nfl",nba:"nba",nhl:"nhl",mlb:"mlb",ncaaf:"ncaaf","ncaa football":"ncaaf","college football":"ncaaf",ncaab:"ncaab","ncaa basketball":"ncaab","college basketball":"ncaab",wnba:"wnba",mls:"mls",epl:"premier-league","premier league":"premier-league","la liga":"la-liga",f1:"f1","formula 1":"f1",motogp:"motogp",ufc:"ufc",mma:"ufc",boxing:"boxing",atp:"atp",wta:"wta",pga:"pga",rugby:"rugby",cricket:"cricket",pdc:"pdc",darts:"pdc",afl:"afl"};
function keyFor(meta){const text=[meta?.id,meta?.name,meta?.description,...(meta?.genres||[])].join(" ").toLowerCase();for(const [a,k] of Object.entries(ALIASES))if(text.includes(a))return k;return "nfl";}
function fallback(meta){return ASSETS[keyFor(meta)];}
function normalizeMeta(meta){if(!meta||typeof meta!=="object")return meta;const poster=/^https:\/\/.*\.png(?:$|[?#])/i.test(String(meta.poster||""))?meta.poster:fallback(meta);const out={...meta,poster,background:fallback(meta),logo:fallback(meta),posterShape:"square"};if(Array.isArray(out.videos))out.videos=out.videos.map(v=>({...v,thumbnail:/^https:\/\/.*\.png(?:$|[?#])/i.test(String(v?.thumbnail||""))?v.thumbnail:poster}));return out;}
function commandCenterMeta(id,name,poster,description,videos){return {id,type:"sport",name,poster,background:poster,logo:poster,posterShape:"square",description,genres:["Sports",id.includes("ufc")?"UFC":"NCAA Football","Command Center"],videos:videos||[],behaviorHints:{defaultVideoId:videos?.[0]?.id}};}
async function gatewayJson(path){const r=await fetch(`http://127.0.0.1:${GATEWAY_PORT}${path}`);if(!r.ok)throw new Error(`gateway ${r.status}`);return r.json();}
async function catalogOverride(path){
  if(path==="/catalog/sport/ufc-home.json"){
    const data=await gatewayJson(path).catch(()=>({metas:[]}));
    const meta=data.metas?.[0];
    if(meta) return {metas:[normalizeMeta(meta)]};
    return {metas:[commandCenterMeta("sport:ufc-home","🥊 UFC • FIGHT NIGHT COMMAND CENTER",UFC,"🔥 UFC FIGHT NIGHT COMMAND CENTER\n\nAuto-updating UFC event hub.\n\n🏆 RANKINGS • 👊 FIGHTERS • 🔥 FIGHT CARDS",[{id:"sport:ufc-rankings",title:"🏆 UFC RANKINGS",released:new Date().toISOString(),thumbnail:UFC},{id:"sport:ufc-fighters",title:"👊 UFC FIGHTERS",released:new Date().toISOString(),thumbnail:UFC}])]};
  }
  if(path==="/catalog/sport/ncaaf.json"){
    const data=await gatewayJson(path).catch(()=>({metas:[]}));
    const games=(data.metas||[]).map(normalizeMeta).slice(0,100);
    const videos=games.flatMap(g=>g.videos||[]).slice(0,100);
    return {metas:[commandCenterMeta("sport:ncaaf-command-center","🏈 NCAA FOOTBALL • COMMAND CENTER",NCAA,`🏈 NCAA FOOTBALL COMMAND CENTER\n\n${games.length} games currently available.\n\n📊 ESPN RANKINGS • 📡 BROADCAST NETWORKS • 🏆 CFP WATCH • 🏟️ GAME CENTER\n\nAuto-updated from the live sports feed.`,videos)]};
  }
  return null;
}
const manifest={id:"com.xsportsx.live",version:VERSION,name:"XSportsX",description:"XSportsX — cinematic live sports hub for Nuvio with live scores, Game Center, UFC Fight Intelligence, and NCAA Football Command Center.",logo:ASSETS.nfl,background:ASSETS.nfl,resources:[{name:"catalog",types:["sport"],idPrefixes:["sport:"]},{name:"meta",types:["sport"],idPrefixes:["sport:"]},{name:"stream",types:["sport"],idPrefixes:["sport:"]}],types:["sport"],idPrefixes:["sport:"],behaviorHints:{configurable:true,configurationRequired:false},catalogs:[
  {type:"sport",id:"sports-leagues",name:"🏆 SPORTS LEAGUES"},{type:"sport",id:"ncaaf",name:"🏈 NCAA FOOTBALL • COMMAND CENTER"},{type:"sport",id:"cfp-watch",name:"🏆 NCAA FOOTBALL • CFP WATCH"},
  {type:"sport",id:"ufc-home",name:"🥊 UFC • FIGHT NIGHT COMMAND CENTER"},{type:"sport",id:"ufc",name:"🔥 UFC • FIGHT CARDS"},{type:"sport",id:"ufc-rankings",name:"🏆 UFC • RANKINGS"},{type:"sport",id:"ufc-fighters",name:"👊 UFC • FIGHTERS"},
  {type:"sport",id:"favorite-teams",name:"⭐ FAVORITE TEAMS"},{type:"sport",id:"sports-news",name:"📰 SPORTS NEWS • ENGLISH"},{type:"sport",id:"live-now",name:"🔥 WHAT'S ON NOW • LIVE"},{type:"sport",id:"starting-soon",name:"⏰ STARTING SOON"},{type:"sport",id:"today",name:"📅 TODAY"}
]};
const child=spawn(process.execPath,["gateway.js"],{env:{...process.env,PORT:String(GATEWAY_PORT),XSPORTSX_BACKEND_PORT:String(BACKEND_PORT)},stdio:"inherit"});
child.on("exit",code=>{if(code&&code!==0)process.exitCode=code;});
function sendJson(res,value,status=200){res.writeHead(status,{"content-type":"application/json; charset=utf-8","cache-control":"no-store","access-control-allow-origin":"*"});res.end(JSON.stringify(value));}
async function proxy(req,res){const path=req.url?.split("?")[0]||"/";try{
  if(path==="/manifest.json")return sendJson(res,manifest);
  if(path==="/health")return sendJson(res,{ok:true,version:VERSION,gateway:GATEWAY_PORT,backend:BACKEND_PORT,baseUrl:BASE});
  if(path==="/catalog/sport/ufc-home.json"||path==="/catalog/sport/ncaaf.json"){const override=await catalogOverride(path);if(override)return sendJson(res,override);}
  if(path==="/meta/sport/ufc-home.json"){const data=await catalogOverride("/catalog/sport/ufc-home.json");return sendJson(res,{meta:data.metas[0]});}
  if(path==="/meta/sport/ncaaf-command-center.json"){const data=await catalogOverride("/catalog/sport/ncaaf.json");return sendJson(res,{meta:data.metas[0]});}
  const upstream=await fetch(`http://127.0.0.1:${GATEWAY_PORT}${req.url}`,{method:req.method,headers:{...req.headers,host:`127.0.0.1:${GATEWAY_PORT}`},body:req.method==="GET"||req.method==="HEAD"?undefined:req});
  const type=upstream.headers.get("content-type")||"application/json";const buf=Buffer.from(await upstream.arrayBuffer());
  if(type.includes("application/json")){try{const payload=JSON.parse(buf.toString("utf8"));if(Array.isArray(payload.metas))payload.metas=payload.metas.map(normalizeMeta);if(payload.meta)payload.meta=normalizeMeta(payload.meta);return sendJson(res,payload,upstream.status);}catch{}}
  res.writeHead(upstream.status,{"content-type":type,"cache-control":upstream.headers.get("cache-control")||"no-store","access-control-allow-origin":"*"});res.end(buf);
}catch(error){sendJson(res,{error:"gateway unavailable",detail:String(error?.message||error)},502);}}
const server=http.createServer(proxy);server.listen(PUBLIC_PORT,"0.0.0.0",()=>console.log(`XSportsX Render entrypoint ${VERSION} listening on ${PUBLIC_PORT}; gateway ${GATEWAY_PORT}; backend ${BACKEND_PORT}`));
