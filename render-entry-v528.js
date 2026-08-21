import http from 'node:http';
import crypto from 'node:crypto';
import fs from 'node:fs';
import { spawn } from 'node:child_process';
import { handleBase64Tool, scanBase64Input } from './base64-link-tool.js';
import { getSourceState as loadSourceState, setSourceState as saveSourceState } from './source-state.js';
import { scanSubreddit } from './reddit-source-monitor.js';

const PUBLIC_PORT=Number(process.env.PORT||7000);
const INTERNAL_PORT=7099;
const PUBLIC_PREFIX='v527';
const BACKEND_PREFIX='v523';
const VERSION='5.0.45';
const BASE=(process.env.BASE_URL||'https://xsportsx.onrender.com').replace(/\/$/,'');
const SECRET=process.env.XSPORTSX_CONFIG_SECRET||'xsportsx-v520-stable-config-key';
const KEY=crypto.createHash('sha256').update(SECRET).digest();

const child=spawn(process.execPath,['sports-router.js'],{env:{...process.env,PORT:String(INTERNAL_PORT),BASE_URL:BASE,XSPORTSX_CONFIG_SECRET:SECRET},stdio:'inherit'});
child.on('error',e=>console.error('[XSportsX] backend error:',e));
child.on('exit',code=>console.error(`[XSportsX] backend exited: ${code}`));

const json=(res,b,status=200)=>{res.writeHead(status,{'content-type':'application/json; charset=utf-8','cache-control':'no-store','access-control-allow-origin':'*','x-xsportsx-version':VERSION});res.end(JSON.stringify(b));};
const norm=s=>String(s||'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
const sourceCache=new Map();

function encryptConfig(v){const iv=crypto.randomBytes(12),c=crypto.createCipheriv('aes-256-gcm',KEY,iv),d=Buffer.concat([c.update(JSON.stringify(v),'utf8'),c.final()]);return Buffer.concat([iv,c.getAuthTag(),d]).toString('base64url');}
function decryptConfig(url){try{const u=new URL(url,'http://localhost'),p=u.pathname.split('/').filter(Boolean),i=p.indexOf(PUBLIC_PREFIX);if(i<0||!p[i+1]||['manifest.json','configure','health','sources'].includes(p[i+1]))return null;const r=Buffer.from(decodeURIComponent(p[i+1]),'base64url');if(r.length<29)return null;const d=crypto.createDecipheriv('aes-256-gcm',KEY,r.subarray(0,12));d.setAuthTag(r.subarray(12,28));const v=JSON.parse(Buffer.concat([d.update(r.subarray(28)),d.final()]).toString('utf8'));if(!v?.server||!v?.username||!v?.password)return null;return{server:String(v.server).replace(/\/+$/,''),username:String(v.username),password:String(v.password),sourceUrl:v.sourceUrl?String(v.sourceUrl).trim():'',subreddit:v.subreddit?String(v.subreddit).trim():''};}catch{return null;}}
async function readBody(req){let b='';for await(const c of req){b+=c;if(b.length>65536)throw new Error('Request too large');}return JSON.parse(b||'{}');}
function rewrite(url){return url.replace(new RegExp(`^/${PUBLIC_PREFIX}(?=/|$)`),`/${BACKEND_PREFIX}`);}

async function discoverReddit(token,config,state){
  if(!config?.subreddit)return state;
  try{
    const result=await scanSubreddit(config.subreddit,{maxPosts:100});
    state.diagnostics={...(result.diagnostics||{}),subreddit:result.subreddit||config.subreddit,lastScan:new Date().toISOString()};
    for(const x of result.discoveries||[]){
      if(state.approved.some(a=>a.url===x.url)||state.rejected.includes(x.url)||state.pending.some(a=>a.url===x.url))continue;
      state.pending.push({url:x.url,type:x.type,healthy:false,details:x.details,postId:x.postId,subreddit:x.subreddit,discoveredAt:x.discoveredAt,credentialPresent:Boolean(x.credentialPresent),credentialFields:x.credentialFields||[]});
    }
    state.pending=state.pending.slice(-500);
    saveSourceState(token,state);
  }catch(e){
    state.diagnostics={...(state.diagnostics||{}),error:String(e.message||e),lastScan:new Date().toISOString()};
    saveSourceState(token,state);
    console.error('[XSportsX] Reddit source discovery failed:',e.message);
  }
  return state;
}

async function getSourceStateByToken(token){
  if(!token)return null;
  const state=loadSourceState(token);
  const config=decryptConfig(`/${PUBLIC_PREFIX}/${encodeURIComponent(token)}/manifest.json`);
  if(!config)return null;
  state.diagnostics=state.diagnostics||{};
  if(config.sourceUrl){
    try{
      const scan=await scanBase64Input({site:config.sourceUrl,health:true});
      state.diagnostics.base64Decoded=scan.decodedCount||0;
      state.diagnostics.destinationsFetched=scan.linkCount||0;
      for(const x of (scan.links||[]).filter(x=>x.ok)){
        const item={url:x.url,type:'direct',healthy:true,status:x.status,latencyMs:x.latencyMs,details:'Discovered from approved source'};
        if(!state.approved.some(a=>a.url===item.url)&&!state.rejected.includes(item.url)&&!state.pending.some(a=>a.url===item.url))state.pending.push(item);
      }
      state.pending=state.pending.slice(-500);
      saveSourceState(token,state);
    }catch(e){state.diagnostics={...(state.diagnostics||{}),sourceError:String(e.message||e)};}
  }
  return discoverReddit(token,config,state);
}

const catalogs=[['sports-command-center','🏆 XSPORTSX • SPORTS COMMAND CENTER'],['live-now','🔴 LIVE NOW'],['starting-soon','⏰ STARTING SOON'],['sports-news-v2','📰 SPORTS NEWS NETWORKS'],['nfl','🏈 NFL'],['ncaaf','🏈 NCAA FOOTBALL'],['nba','🏀 NBA'],['nhl','🏒 NHL'],['mlb','⚾ MLB'],['ufc-v2','🥊 UFC COMMAND CENTER'],['soccer','⚽ SOCCER'],['iptv-live','📡 MY IPTV • LIVE TV']];
const baseManifest={id:'com.xsportsx.sports.epg',version:VERSION,name:'XSportsX Sports Command Center',description:'Fast sports catalogs, authorized Xtream resolution, and operator-approved source discovery.',resources:[{name:'catalog',types:['channel']},{name:'meta',types:['channel']},{name:'stream',types:['channel']}],types:['channel'],idPrefixes:['sport:','xtream:','news:','live:'],catalogs:catalogs.map(([id,name])=>({type:'channel',id,name,extra:[],showInHome:true})),behaviorHints:{configurable:true,configurationRequired:true}};
function manifest(configured){return configured?{...baseManifest,behaviorHints:{configurable:false,configurationRequired:false}}:{...baseManifest,config:[{key:'server',type:'text',title:'Xtream Server URL',required:true},{key:'username',type:'text',title:'Xtream Username',required:true},{key:'password',type:'password',title:'Xtream Password',required:true},{key:'sourceUrl',type:'text',title:'📡 Approved Source URL',required:false},{key:'subreddit',type:'text',title:'👽 Authorized Reddit Subreddit',required:false,description:'Optional subreddit used for source discovery and approval.'}]};}

const configureHtml=`<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>XSportsX Setup</title><style>*{box-sizing:border-box}body{margin:0;background:#0b0f14;color:#eef2f7;font:16px system-ui}.wrap{max-width:560px;margin:auto;padding:28px 18px}.card{background:#151b23;border:1px solid #293241;border-radius:16px;padding:20px}label{display:block;font-weight:700;margin:16px 0 7px}input{width:100%;padding:14px;border-radius:10px;border:1px solid #394454;background:#0e141b;color:#fff;font-size:16px}.hint{font-size:13px;color:#8f9baa;margin-top:6px;line-height:1.4}.btn{display:block;width:100%;margin-top:22px;padding:14px;border:0;border-radius:10px;background:#4b8cff;color:#fff;font-size:16px;font-weight:800}.result{display:none;margin-top:18px;padding:14px;border-radius:10px;background:#10291a;border:1px solid #245c35}.result a{color:#8fc7ff;font-weight:700;word-break:break-all}.error{color:#ff7b72;margin-top:12px}</style></head><body><main class="wrap"><h1>🏆 XSPORTSX</h1><p>Fast sports + authorized source discovery.</p><div class="card"><label>Xtream Server URL</label><input id="server" placeholder="https://your-server.com"><label>Xtream Username</label><input id="username"><label>Xtream Password</label><input id="password" type="password"><label>📡 Approved Source URL</label><input id="source" placeholder="https://your-authorized-source.example"><div class="hint">Optional. Scans the page/feed for Base64 and public links.</div><label>👽 Authorized Reddit Subreddit</label><input id="subreddit" placeholder="https://www.reddit.com/r/your_subreddit"><div class="hint">Posts are scanned for Base64, then decoded destinations are followed. New sources stay pending until you approve them.</div><button class="btn" onclick="install()">Create My XSportsX Addon</button><div id="err" class="error"></div><div id="result" class="result"><b>✅ Configured</b><p><a id="addon"></a></p><p><a id="manage"></a></p></div></div></main><script>async function install(){const body={server:server.value.trim(),username:username.value.trim(),password:password.value,sourceUrl:source.value.trim(),subreddit:subreddit.value.trim()};err.textContent='';if(!body.server||!body.username||!body.password){err.textContent='Enter your Xtream server, username, and password.';return}try{const r=await fetch(location.pathname,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)}),j=await r.json();if(!r.ok)throw Error(j.error||'Setup failed');addon.href=j.addonUrl;addon.textContent=j.addonUrl;manage.href=j.manageUrl;manage.textContent='Open Source Manager';result.style.display='block'}catch(e){err.textContent=e.message}}</script></body></html>`;

function safeUrl(url){try{const u=new URL(String(url));return ['http:','https:'].includes(u.protocol)&&!u.hostname.match(/^(localhost|127\.|10\.|192\.168\.)/i);}catch{return false;}}
function sanitizeSource(item){const x={...item};if(typeof x.url==='string'){try{const u=new URL(x.url);if(u.username||u.password||u.searchParams.has('username')||u.searchParams.has('password')||u.searchParams.has('user')||u.searchParams.has('pass')){x.url=u.origin+u.pathname;x.credentialPresent=true;x.details=(x.details||'Discovered source')+' • credentials protected';}}catch{}}return x;}

const server=http.createServer(async(req,res)=>{
  try{
    const u=new URL(req.url||'/',`http://${req.headers.host||'localhost'}`),p=u.pathname;
    if(p==='/health'||p===`/${PUBLIC_PREFIX}/health`)return json(res,{ok:true,version:VERSION,service:'xsportsx',backend:'sports-router',redditDiscovery:true});
    if((p==='/configure'||p===`/${PUBLIC_PREFIX}/configure`)&&req.method==='GET'){res.writeHead(200,{'content-type':'text/html; charset=utf-8','cache-control':'no-store'});return res.end(configureHtml);}
    if((p==='/configure'||p===`/${PUBLIC_PREFIX}/configure`)&&req.method==='POST'){
      const v=await readBody(req);if(!v.server||!v.username||!v.password)throw new Error('Xtream server, username, and password are required');
      if(v.sourceUrl&&!/^https?:\/\//i.test(String(v.sourceUrl)))throw new Error('Source URL must start with http:// or https://');
      if(v.subreddit&&!/reddit\.com\/r\/|^r\//i.test(String(v.subreddit)))throw new Error('Enter a valid Reddit subreddit URL');
      const token=encryptConfig({server:String(v.server).replace(/\/+$/,''),username:String(v.username),password:String(v.password),sourceUrl:String(v.sourceUrl||'').trim(),subreddit:String(v.subreddit||'').trim()});
      return json(res,{ok:true,addonUrl:`${BASE}/${PUBLIC_PREFIX}/${encodeURIComponent(token)}/manifest.json`,manageUrl:`${BASE}/${PUBLIC_PREFIX}/sources/${encodeURIComponent(token)}`});
    }
    if(p===`/${PUBLIC_PREFIX}/manifest.json`||p==='/manifest.json')return json(res,manifest(false));
    if(p.startsWith(`/${PUBLIC_PREFIX}/`)&&p.endsWith('/manifest.json'))return json(res,manifest(true));
    const sourcePrefix=`/${PUBLIC_PREFIX}/sources/`;
    if(p.startsWith(sourcePrefix)){
      const token=decodeURIComponent(p.slice(sourcePrefix.length).split('/')[0]);
      if(!token)return json(res,{error:'Missing source token'},400);
      if(req.method==='GET'){
        const state=await getSourceStateByToken(token);
        if(!state)return json(res,{error:'Invalid or expired configuration'},404);
        return json(res,state);
      }
      if(req.method==='POST'){
        const body=await readBody(req),state=loadSourceState(token);let url=String(body.url||'').trim();
        if(!safeUrl(url))return json(res,{error:'Invalid source URL'},400);
        url=sanitizeSource({url}).url;
        if(body.action==='approve'){
          state.pending=state.pending.filter(x=>x.url!==url);
          state.rejected=state.rejected.filter(x=>x!==url);
          if(!state.approved.some(x=>x.url===url))state.approved.push(sanitizeSource({url,type:body.type||'source',healthy:true,details:'Operator approved source'}));
        }else if(body.action==='reject'){
          state.pending=state.pending.filter(x=>x.url!==url);state.approved=state.approved.filter(x=>x.url!==url);if(!state.rejected.includes(url))state.rejected.push(url);
        }else if(body.action==='revoke'){
          state.approved=state.approved.filter(x=>x.url!==url);if(!state.rejected.includes(url))state.rejected.push(url);
        }else return json(res,{error:'Unknown action'},400);
        return json(res,saveSourceState(token,state));
      }
    }
    if(p.startsWith(`/${PUBLIC_PREFIX}/`)){
      const target=new URL(rewrite(req.url||'/'),`http://127.0.0.1:${INTERNAL_PORT}`);
      const up=http.request(target,{method:req.method,headers:{...req.headers,host:`127.0.0.1:${INTERNAL_PORT}`,connection:'keep-alive'}},ur=>{let data='';ur.setEncoding('utf8');ur.on('data',x=>data+=x);ur.on('end',()=>{const h={...ur.headers,'x-xsportsx-version':VERSION};delete h['content-length'];res.writeHead(ur.statusCode||502,h);res.end(data);});});
      up.on('error',e=>{if(!res.headersSent)res.writeHead(502,{'content-type':'application/json'});if(!res.writableEnded)res.end(JSON.stringify({error:'XSportsX backend unavailable',detail:String(e.message||e)}));});
      req.pipe(up);return;
    }
    if(p.endsWith('/assets/ufc.svg')){res.writeHead(200,{'content-type':'image/svg+xml','cache-control':'public,max-age=86400'});return res.end('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 300"><rect width="800" height="300" rx="30" fill="#111"/><text x="400" y="190" text-anchor="middle" font-family="Arial" font-weight="900" font-size="150" fill="#fff">UFC</text></svg>');}
    return json(res,{error:'Not found'},404);
  }catch(e){console.error('[XSportsX gateway]',e);return json(res,{error:String(e.message||e)},502);}
});
server.keepAliveTimeout=120000;server.headersTimeout=125000;server.requestTimeout=120000;
server.listen(PUBLIC_PORT,'0.0.0.0',()=>console.log(`XSportsX ${VERSION} gateway ${PUBLIC_PREFIX} listening on ${PUBLIC_PORT}`));
