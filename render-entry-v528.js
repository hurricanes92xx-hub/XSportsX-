import http from "node:http";
import crypto from "node:crypto";
import { spawn } from "node:child_process";

const PUBLIC_PORT=Number(process.env.PORT||7000);
const INTERNAL_PORT=7099;
const PUBLIC_PREFIX="v527";
const BACKEND_PREFIX="v523";
const VERSION="5.0.32";
const BASE=(process.env.BASE_URL||"https://xsportsx.onrender.com").replace(/\/$/,"");
const SECRET=process.env.XSPORTSX_CONFIG_SECRET||"xsportsx-v520-stable-config-key";
const KEY=crypto.createHash("sha256").update(SECRET).digest();

const child=spawn(process.execPath,["sports-router.js"],{env:{...process.env,PORT:String(INTERNAL_PORT),BASE_URL:BASE,XSPORTSX_CONFIG_SECRET:SECRET},stdio:"inherit"});
child.on("error",e=>console.error("XSportsX backend error:",e));
child.on("exit",code=>process.exit(code??1));

const encrypt=v=>{const iv=crypto.randomBytes(12),c=crypto.createCipheriv("aes-256-gcm",KEY,iv),d=Buffer.concat([c.update(JSON.stringify(v),"utf8"),c.final()]);return Buffer.concat([iv,c.getAuthTag(),d]).toString("base64url")};
const json=(res,b,status=200,maxAge=0)=>{res.writeHead(status,{"content-type":"application/json; charset=utf-8","cache-control":maxAge?`public,max-age=${maxAge},stale-while-revalidate=30`:"no-store","access-control-allow-origin":"*","x-xsportsx-version":VERSION});res.end(JSON.stringify(b));};

const catalogs=[
 ["sports-command-center","🏆 XSPORTSX • SPORTS COMMAND CENTER"],["live-now","🔴 LIVE NOW"],["starting-soon","⏰ STARTING SOON"],["sports-news-v2","📰 SPORTS NEWS NETWORKS"],["nfl","🏈 NFL"],["ncaaf","🏈 NCAA FOOTBALL"],["nba","🏀 NBA"],["nhl","🏒 NHL"],["mlb","⚾ MLB"],["ufc-v2","🥊 UFC COMMAND CENTER"],["soccer","⚽ SOCCER"],["iptv-live","📡 MY IPTV • LIVE TV"]
];
const baseManifest={id:"com.xsportsx.sports.epg.v532",version:VERSION,name:"XSportsX Sports Command Center",description:"Fast sports EPG with live sports and authorized Xtream source resolution.",resources:[{name:"catalog",types:["channel"]},{name:"meta",types:["channel"]},{name:"stream",types:["channel"]}],types:["channel"],idPrefixes:["sport:","xtream:","news:","live:"],catalogs:catalogs.map(([id,name])=>({type:"channel",id,name,extra:[]})),behaviorHints:{configurable:true,configurationRequired:true}};
const manifest=configured=>configured?{...baseManifest,behaviorHints:{configurable:false,configurationRequired:false}}:{...baseManifest,config:[{key:"server",type:"text",title:"Xtream Server URL",required:true},{key:"username",type:"text",title:"Xtream Username",required:true},{key:"password",type:"password",title:"Xtream Password",required:true}]};

function fallbackCatalog(id){
 const names={nfl:"NFL",ncaaf:"NCAA Football",nba:"NBA",nhl:"NHL",mlb:"MLB",soccer:"Soccer",ufc:"UFC"};
 const icons={nfl:"🏈",ncaaf:"🏈",nba:"🏀",nhl:"🏒",mlb:"⚾",soccer:"⚽",ufc:"🥊"};
 const league=id.endsWith("-v2")?id.slice(0,-3):id;
 if(names[league])return {metas:[{id:`sport:hub:${league}`,type:"channel",name:`${icons[league]} ${names[league]} — Sports Hub`,poster:"",background:"",description:`${names[league]} events and live coverage.`,genres:["Sports",names[league]],league}]};
 if(id==="sports-command-center")return {metas:Object.entries(names).map(([k,n])=>({id:`sport:hub:${k}`,type:"channel",name:`${icons[k]} ${n}`,description:`${n} sports hub`,genres:["Sports",n],league:k}))};
 if(id==="sports-news-v2")return {metas:[{id:"news:all-sports-news",type:"channel",name:"📰 Sports News Networks",description:"Sports news channels from your authorized Xtream provider.",genres:["Sports News"]}]};
 if(id==="live-now")return {metas:[{id:"live:none",type:"channel",name:"🔴 Live Now",description:"Live event metadata is refreshing.",genres:["Sports","Live"]}]};
 if(id==="starting-soon")return {metas:[{id:"soon:none",type:"channel",name:"⏰ Starting Soon",description:"Upcoming event metadata is refreshing.",genres:["Sports","Upcoming"]}]};
 return {metas:[]};
}

function configure(req,res){
 if(req.method==="GET"){
  res.writeHead(200,{"content-type":"text/html; charset=utf-8","cache-control":"no-store"});
  return res.end(`<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>XSportsX Xtream Login</title></head><body style="background:#08090c;color:#fff;font:16px system-ui;max-width:520px;margin:auto;padding:28px"><h1>XSportsX ${VERSION}</h1><p>Enter your authorized Xtream account.</p><form method="post"><input name="server" placeholder="Xtream Server URL (https://example.com)" required style="display:block;width:100%;box-sizing:border-box;padding:14px;margin:10px 0"><input name="username" placeholder="Username" required style="display:block;width:100%;box-sizing:border-box;padding:14px;margin:10px 0"><input name="password" type="password" placeholder="Password" required style="display:block;width:100%;box-sizing:border-box;padding:14px;margin:10px 0"><button style="width:100%;padding:15px;font-weight:700">Generate Nuvio Configuration</button></form></body></html>`);
 }
 let body="";req.on("data",x=>body+=x);req.on("end",()=>{
  const f=new URLSearchParams(body),server=String(f.get("server")||"").trim().replace(/\/+$/,""),username=String(f.get("username")||"").trim(),password=String(f.get("password")||"");
  if(!/^https?:\/\//i.test(server)||!username||!password)return json(res,{error:"Enter a valid http(s) Xtream server, username and password."},400);
  const token=encrypt({server,username,password}),url=`${BASE}/${PUBLIC_PREFIX}/${token}/manifest.json`;
  res.writeHead(200,{"content-type":"text/html; charset=utf-8","cache-control":"no-store"});
  res.end(`<!doctype html><html><body style="background:#08090c;color:#fff;font:16px system-ui;max-width:650px;margin:auto;padding:28px"><h1>XSportsX Ready</h1><p>Copy this complete configuration URL into Nuvio:</p><textarea readonly onclick="this.select()" style="width:100%;height:110px;box-sizing:border-box;padding:12px">${url}</textarea><p><a href="${url}" style="color:#ff9800">Test manifest</a></p></body></html>`);
 });
}

function rewrite(url){return url.replace(new RegExp(`^/${PUBLIC_PREFIX}(?=/|$)`),`/${BACKEND_PREFIX}`);}
const server=http.createServer((req,res)=>{
 try{
  const u=new URL(req.url||"/","http://localhost"),p=u.pathname;
  if(p==="/health"||p===`/${PUBLIC_PREFIX}/health`)return json(res,{ok:true,version:VERSION,service:"xsportsx",backend:"sports-router",prefix:PUBLIC_PREFIX});
  if(p===`/${PUBLIC_PREFIX}/configure`)return configure(req,res);
  if(p===`/${PUBLIC_PREFIX}/manifest.json`)return json(res,manifest(false));
  if(p.startsWith(`/${PUBLIC_PREFIX}/`)&&p.endsWith("/manifest.json"))return json(res,manifest(true));
  const target=new URL(rewrite(req.url||"/"),`http://127.0.0.1:${INTERNAL_PORT}`);
  const up=http.request(target,{method:req.method,headers:{...req.headers,host:`127.0.0.1:${INTERNAL_PORT}`,connection:"keep-alive"}},ur=>{
   let data="";ur.setEncoding("utf8");ur.on("data",x=>data+=x);ur.on("end",()=>{
    const isCatalog=target.pathname.includes("/catalog/channel/");
    if(isCatalog){
     const id=target.pathname.split("/catalog/channel/")[1].replace(/\.json$/i,"");
     try{const parsed=JSON.parse(data);if(ur.statusCode===200&&Array.isArray(parsed.metas)&&parsed.metas.length>0){}else return json(res,fallbackCatalog(id),200,10)}catch{return json(res,fallbackCatalog(id),200,10)}
    }
    const h={...ur.headers,"x-xsportsx-version":VERSION};delete h["content-length"];res.writeHead(ur.statusCode||502,h);res.end(data);
   });
  });
  up.on("error",e=>{if(!res.headersSent)res.writeHead(502,{"content-type":"application/json"});res.end(JSON.stringify({error:"XSportsX backend unavailable",detail:String(e.message||e)}));});
  req.pipe(up);
 }catch(e){json(res,{error:String(e.message||e)},502);}
});
server.keepAliveTimeout=120000;server.headersTimeout=125000;server.requestTimeout=120000;server.listen(PUBLIC_PORT,"0.0.0.0",()=>console.log(`XSportsX ${VERSION} gateway ${PUBLIC_PREFIX} listening on ${PUBLIC_PORT}`));
