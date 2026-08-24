const fs=require('fs');
const Module=require('module');
const http=require('http');
const crypto=require('crypto');
const {URL}=require('url');

const publicPort=Number(process.env.PORT||10000);
const internalPort=publicPort+1;
const SECRET=process.env.XSPORTSX_CONFIG_SECRET||'change-this-in-render';
const KEY=crypto.createHash('sha256').update(SECRET).digest();
const appPath=__dirname+'/app98.js';
let source=fs.readFileSync(appPath,'utf8')
  .replace("const VERSION='9.8.0'", "const VERSION='9.8.3'")
  .replace("id:'community.xsportsx'", "id:'community.xsportsx983'");

// Render HTTPS/security headers.
const oldHdr="function hdr(r,t='application/json; charset=utf-8'){r.setHeader('access-control-allow-origin','*');r.setHeader('access-control-allow-methods','GET,POST,OPTIONS');r.setHeader('access-control-allow-headers','content-type');r.setHeader('cache-control','no-store');r.setHeader('x-xsportsx-version',VERSION);r.setHeader('content-type',t)}";
const newHdr="function hdr(r,t='application/json; charset=utf-8'){r.setHeader('access-control-allow-origin','*');r.setHeader('access-control-allow-methods','GET,POST,OPTIONS');r.setHeader('access-control-allow-headers','content-type');r.setHeader('cache-control','no-store');r.setHeader('x-xsportsx-version',VERSION);r.setHeader('strict-transport-security','max-age=31536000; includeSubDomains');r.setHeader('content-security-policy','upgrade-insecure-requests');r.setHeader('x-content-type-options','nosniff');r.setHeader('referrer-policy','strict-origin-when-cross-origin');r.setHeader('content-type',t)}";
if(source.includes(oldHdr))source=source.replace(oldHdr,newHdr);

// Use a real forward window for ESPN so NFL/NCAA catalogs show upcoming games,
// not only today's scoreboard.
const oldEspn="async function espn(id){const l=L(id);if(!l)return[];try{const d=await get(`https://site.api.espn.com/apis/site/v2/sports/${l[3]}/${l[4]}/scoreboard?limit=100`);return(d.events||[]).map(e=>espnNorm(id,e))}catch{return[]}}";
const newEspn="async function espn(id){const l=L(id);if(!l)return[];try{const now=new Date(),end=new Date(Date.now()+14*86400000),fmt=d=>d.toISOString().slice(0,10).replace(/-/g,'');const base=`https://site.api.espn.com/apis/site/v2/sports/${l[3]}/${l[4]}/scoreboard?limit=100&dates=${fmt(now)}-${fmt(end)}`;const d=await get(base,10000);return(d.events||[]).map(e=>espnNorm(id,e)).filter(Boolean)}catch{return[]}}";
if(source.includes(oldEspn))source=source.replace(oldEspn,newEspn);

// Never manufacture generic Away/Home placeholders.
const oldEspnNorm="function espnNorm(id,e){const c=e.competitions?.[0],t=c?.competitors||[],a=t.find(x=>x.homeAway==='away'),h=t.find(x=>x.homeAway==='home'),s=c?.status?.type||{};return{league:id,source:'ESPN',sourceId:String(e.id),away:a?.team?.displayName||t[0]?.team?.displayName,home:h?.team?.displayName||t[1]?.team?.displayName,start:e.date,status:s.completed?'final':/postponed|cancel/i.test(s.name||'')?'postponed':s.state==='in'?'live':'scheduled',broadcasts:(c?.broadcasts||[]).flatMap(x=>[...(x.names||[]),x.market,x.type?.shortName,x.type?.longName]).filter(Boolean)}}";
const newEspnNorm="function espnNorm(id,e){const c=e.competitions?.[0],t=c?.competitors||[],a=t.find(x=>x.homeAway==='away'),h=t.find(x=>x.homeAway==='home'),s=c?.status?.type||{},away=a?.team?.displayName||t[0]?.team?.displayName,home=h?.team?.displayName||t[1]?.team?.displayName;if(!away||!home||/^(away|home|tbd)$/i.test(away)||/^(away|home|tbd)$/i.test(home))return null;return{league:id,source:'ESPN',sourceId:String(e.id),away,home,start:e.date,status:s.completed?'final':/postponed|cancel/i.test(s.name||'')?'postponed':s.state==='in'?'live':'scheduled',broadcasts:(c?.broadcasts||[]).flatMap(x=>[...(x.names||[]),x.market,x.type?.shortName,x.type?.longName]).filter(Boolean)}}";
if(source.includes(oldEspnNorm))source=source.replace(oldEspnNorm,newEspnNorm);

// Stable event IDs: base64url the source ID so Nuvio never mangles colons.
const oldEventMeta="function eventMeta(id,e,base){const l=LEAGUE(id);return{id:`sports:${id}:event:${encodeURIComponent(e.sourceId||eventKey(e))}`,type:'tv',name:`${e.away} vs ${e.home}`,poster:`${base}/artwork.svg`,posterShape:'landscape',releaseInfo:new Date(e.start).toISOString().slice(0,10),description:`${e.status==='live'?'LIVE • ':''}${new Date(e.start).toLocaleString()} • ${l[1]} • ${[...(e.broadcasts||[])].slice(0,4).join(', ')}`,genres:[l[1]]}}";
const newEventMeta="function eventMeta(id,e,base){const l=LEAGUE(id),key=Buffer.from(String(e.sourceId||eventKey(e))).toString('base64url');return{id:`sports:${id}:event:${key}`,type:'tv',name:`${e.away} vs ${e.home}`,poster:`${base}/artwork.svg`,posterShape:'landscape',releaseInfo:new Date(e.start).toISOString().slice(0,10),description:`${e.status==='live'?'LIVE • ':''}${new Date(e.start).toLocaleString()} • ${l[1]} • ${[...(e.broadcasts||[])].slice(0,6).join(', ')}`,genres:[l[1]]}}";
if(source.includes(oldEventMeta))source=source.replace(oldEventMeta,newEventMeta);

// Resolve both new base64 IDs and older event IDs.
const oldMetaHandler="if(parts[1]==='meta'&&parts[2]==='tv'&&parts[3]){const rid=parts[3].replace(/\\.json$/,'');const id=rid.split(':')[1]||c.sports[0];const ev=await schedules(id);const e=ev.find(x=>String(x.sourceId)===decodeURIComponent(rid.split(':').slice(2).join(':')));return json(res,200,{meta:e?eventMeta(id,e,u.origin):null})}";
const newMetaHandler="if(parts[1]==='meta'&&parts[2]==='tv'&&parts[3]){const rid=parts[3].replace(/\\.json$/,'');const bits=rid.split(':');const id=bits[1]||c.sports[0];if(!VALID.has(id))return json(res,200,{meta:null});let raw=bits.slice(2).join(':').replace(/^event:/,'');try{raw=Buffer.from(raw,'base64url').toString('utf8')}catch{}const ev=await schedules(id);const e=ev.find(x=>String(x.sourceId)===decodeURIComponent(raw)||eventKey(x)===decodeURIComponent(raw));return json(res,200,{meta:e?eventMeta(id,e,u.origin):null})}";
if(source.includes(oldMetaHandler))source=source.replace(oldMetaHandler,newMetaHandler);

const oldStreamHandler="if(parts[1]==='stream'&&parts[2]==='tv'&&parts[3]){const rid=parts[3].replace(/\\.json$/,'');const bits=rid.split(':');const id=bits[1];if(!VALID.has(id))return json(res,200,{streams:[]});const raw=bits.slice(2).join(':').replace(/^event:/,'');return json(res,200,{streams:await streamsForEvent(c,id,raw,u.origin)})}";
const newStreamHandler="if(parts[1]==='stream'&&parts[2]==='tv'&&parts[3]){const rid=parts[3].replace(/\\.json$/,'');const bits=rid.split(':');const id=bits[1];if(!VALID.has(id))return json(res,200,{streams:[]});let raw=bits.slice(2).join(':').replace(/^event:/,'');try{raw=Buffer.from(raw,'base64url').toString('utf8')}catch{}return json(res,200,{streams:await streamsForEvent(c,id,raw,u.origin)})}";
if(source.includes(oldStreamHandler))source=source.replace(oldStreamHandler,newStreamHandler);

const oldStreamsForEvent="let decoded=decodeURIComponent(rawId);let e=ev.find(x=>String(x.sourceId)===decoded);if(!e){const n=decoded.split(':');const guess=norm(n.slice(-1)[0]);e=ev.find(x=>norm(`${x.away} ${x.home}`)===guess)}if(!e)return[];";
const newStreamsForEvent="let decoded=decodeURIComponent(rawId);let e=ev.find(x=>String(x.sourceId)===decoded||eventKey(x)===decoded);if(!e){const n=decoded.split(':');const guess=norm(n.slice(-1)[0]);e=ev.find(x=>norm(`${x.away} ${x.home}`)===guess)}if(!e)return[];";
if(source.includes(oldStreamsForEvent))source=source.replace(oldStreamsForEvent,newStreamsForEvent);

// Make absolute URLs HTTPS-aware behind Render.
source=source.replace(/const u=new URL\(req\.url,([^\n;]+)\)/g,"const u=new URL(req.url,`https://${req.headers.host||'localhost'}`)");

// Run the addon on an internal port; the public proxy below enforces the
// selected-league manifest/catalog boundary without altering event streams.
process.env.PORT=String(internalPort);
const m=new Module(appPath,module);m.filename=appPath;m.paths=module.paths;m._compile(source,m.filename);

function decryptConfig(token){try{const[a,b,c]=String(token||'').split('.');if(!a||!b||!c)return null;const d=crypto.createDecipheriv('aes-256-gcm',KEY,Buffer.from(a,'base64url'));d.setAuthTag(Buffer.from(b,'base64url'));return JSON.parse(Buffer.concat([d.update(Buffer.from(c,'base64url')),d.final()]).toString('utf8'))}catch{return null}}
function tokenFrom(raw){const u=new URL(raw||'/','http://local');const p=u.pathname.split('/').filter(Boolean);if(p[0]==='v527')return p[1]||'';const i=p.findIndex(x=>x==='manifest.json'||x==='catalog'||x.startsWith('catalog')||x==='meta'||x.startsWith('meta')||x==='stream'||x.startsWith('stream'));if(i>0)return p[i-1];return u.searchParams.get('config')||''}
function selected(token){const c=decryptConfig(token),s=Array.isArray(c?.sports)?c.sports.map(String).filter(x=>VALID_LEAGUE.has(x)):[];return new Set(s)}
const VALID_LEAGUE=new Set(['nfl','ncaaf','nba','wnba','ncaab','mlb','nhl','mls','epl','ucl','laliga','seriea','bundesliga','ligue1','ufc','boxing']);
function catalogLeague(id){const n=String(id||'').toLowerCase();for(const x of VALID_LEAGUE)if(n===x||n.endsWith(':'+x)||n.includes(`:${x}:`)||n.includes(`-${x}`))return x;return ''}
function filterJson(body,token,path){const s=selected(token);if(!s.size||!body||typeof body!=='object')return body;if(path==='/manifest.json'&&Array.isArray(body.catalogs)){body.catalogs=body.catalogs.filter(c=>{const l=catalogLeague(c.id);return l?s.has(l):false});body.version='9.8.3';body.id=`community.xsportsx983.${crypto.createHash('sha256').update(token).digest('hex').slice(0,16)}`;}if(Array.isArray(body.metas))body.metas=body.metas.filter(m=>{const id=String(m?.id||'');const l=id.split(':')[1]||catalogLeague(id);return !l||s.has(l)});return body}

const proxy=http.createServer((req,res)=>{try{const token=tokenFrom(req.url),u=new URL(req.url||'/','http://local');const path=u.pathname.replace(/^\/v527\//,'/');const isJson=path==='/manifest.json'||path.startsWith('/catalog/');const upstream=http.request({hostname:'127.0.0.1',port:internalPort,path:req.url,method:req.method,headers:{...req.headers,host:`127.0.0.1:${internalPort}`}},r=>{const ct=String(r.headers['content-type']||'');if(!token||!isJson||!ct.includes('application/json')){res.writeHead(r.statusCode||502,{...r.headers,'x-xsportsx-version':'9.8.3'});return r.pipe(res)}const chunks=[];r.on('data',x=>chunks.push(x));r.on('end',()=>{try{const body=filterJson(JSON.parse(Buffer.concat(chunks).toString('utf8')),token,path);const out=Buffer.from(JSON.stringify(body));const h={...r.headers,'content-length':String(out.length),'x-xsportsx-version':'9.8.3'};delete h['transfer-encoding'];res.writeHead(r.statusCode||502,h);res.end(out)}catch{res.writeHead(r.statusCode||502,{...r.headers,'x-xsportsx-version':'9.8.3'});res.end(Buffer.concat(chunks))}})});upstream.on('error',e=>{res.statusCode=502;res.end(e.message)});req.pipe(upstream)}catch(e){res.statusCode=400;res.end(e.message)}});proxy.listen(publicPort,'0.0.0.0',()=>console.log(`XSportsX 9.8.3 public ${publicPort}, internal ${internalPort}`));
