const http = require('http');
const crypto = require('crypto');
const { URL } = require('url');

const PORT = Number(process.env.PORT || 10000);
const SECRET = process.env.XSPORTSX_CONFIG_SECRET || 'change-this-in-render';
const KEY = crypto.createHash('sha256').update(SECRET).digest();
const VERSION = '9.3.0';
const CACHE = new Map();

const LEAGUES = [
  ['nfl', 'NFL', '🏈', 'football', 'nfl'], ['ncaaf', 'NCAA Football', '🏈', 'football', 'college-football'],
  ['nba', 'NBA', '🏀', 'basketball', 'nba'], ['wnba', 'WNBA', '🏀', 'basketball', 'wnba'],
  ['ncaab', 'NCAA Basketball', '🏀', 'basketball', 'mens-college-basketball'], ['mlb', 'MLB', '⚾', 'baseball', 'mlb'],
  ['nhl', 'NHL', '🏒', 'hockey', 'nhl'], ['mls', 'MLS', '⚽', 'soccer', 'usa.1'],
  ['epl', 'Premier League', '⚽', 'soccer', 'eng.1'], ['ucl', 'UEFA Champions League', '⚽', 'soccer', 'uefa.champions'],
  ['laliga', 'LaLiga', '⚽', 'soccer', 'esp.1'], ['seriea', 'Serie A', '⚽', 'soccer', 'ita.1'],
  ['bundesliga', 'Bundesliga', '⚽', 'soccer', 'ger.1'], ['ligue1', 'Ligue 1', '⚽', 'soccer', 'fra.1'],
  ['ufc', 'UFC', '🥊', 'mma', 'ufc'], ['boxing', 'Boxing', '🥊', 'boxing', 'boxing']
];
const VALID = new Set(LEAGUES.map(([id]) => id));

function headers(res, type = 'application/json; charset=utf-8') {
  res.setHeader('access-control-allow-origin', '*');
  res.setHeader('access-control-allow-methods', 'GET,POST,OPTIONS');
  res.setHeader('access-control-allow-headers', 'content-type');
  res.setHeader('x-xsportsx-version', VERSION);
  res.setHeader('cache-control', 'no-store');
  res.setHeader('content-type', type);
}
function json(res, status, body) {
  const text = JSON.stringify(body);
  headers(res); res.statusCode = status;
  res.setHeader('content-length', Buffer.byteLength(text)); res.end(text);
}
function encrypt(value) {
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv('aes-256-gcm', KEY, iv);
  const body = Buffer.concat([cipher.update(JSON.stringify(value), 'utf8'), cipher.final()]);
  return [iv, cipher.getAuthTag(), body].map(b => b.toString('base64url')).join('.');
}
function decrypt(token) {
  try {
    const [iv, tag, body] = String(token || '').split('.');
    if (!iv || !tag || !body) return null;
    const decipher = crypto.createDecipheriv('aes-256-gcm', KEY, Buffer.from(iv, 'base64url'));
    decipher.setAuthTag(Buffer.from(tag, 'base64url'));
    return JSON.parse(Buffer.concat([decipher.update(Buffer.from(body, 'base64url')), decipher.final()]).toString('utf8'));
  } catch { return null; }
}
function normalizeXtreamUrl(value) {
  let s = String(value || '').trim(); if (!s) return '';
  try {
    const u = new URL(s); u.search = ''; u.hash = '';
    u.pathname = u.pathname.replace(/\/+$/, '').replace(/\/player_api\.php$/i, '');
    return u.toString().replace(/\/$/, '');
  } catch { return ''; }
}
function manifest(base, config) {
  return {
    id: 'community.xsportsx', version: VERSION, name: 'XSportsX',
    description: 'Fast live sports from your own Xtream source.', types: ['tv'],
    resources: [
      { name: 'catalog', types: ['tv'] },
      { name: 'meta', types: ['tv'], idPrefixes: ['sports:'] },
      { name: 'stream', types: ['tv'], idPrefixes: ['sports:'] }
    ],
    catalogs: config.sports.map(id => { const l = LEAGUES.find(x => x[0] === id); return { type: 'tv', id: `sports:${id}`, name: `${l[2]} ${l[1]}`, extra: [{ name: 'search', isRequired: false }] }; }),
    behaviorHints: { configurable: false, configurationRequired: false }, logo: `${base}/artwork.svg`
  };
}
function artwork(res) {
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512"><rect width="100%" height="100%" fill="#070b12"/><text x="50%" y="48%" text-anchor="middle" fill="white" font-family="Arial" font-size="64" font-weight="700">XSPORTSX</text><text x="50%" y="58%" text-anchor="middle" fill="#ff344b" font-family="Arial" font-size="28">LIVE SPORTS</text></svg>';
  headers(res, 'image/svg+xml'); res.setHeader('cache-control', 'public,max-age=86400'); res.end(svg);
}
function configPage(base) {
  const cards = LEAGUES.map(([id, name, emoji]) => `<button class="league" type="button" data-id="${id}" aria-pressed="false"><span>${emoji}</span><strong>${name}</strong></button>`).join('');
  return `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"><title>XSportsX 9.3</title><style>*{box-sizing:border-box}body{margin:0;background:#070b12;color:#fff;font-family:system-ui,-apple-system,Segoe UI,sans-serif}main{max-width:720px;margin:auto;padding:20px}.hero,.panel{background:#0d1420;border:1px solid #25344a;border-radius:18px;padding:20px;margin-bottom:16px}.hero h1{margin:0 0 4px;font-size:32px}.muted{color:#91a0b5}.league{width:100%;display:flex;align-items:center;gap:14px;text-align:left;padding:15px;margin:7px 0;border-radius:14px;border:1px solid #2a3a50;background:#121b29;color:#fff;font-size:17px;cursor:pointer;touch-action:manipulation}.league span{font-size:24px}.league[aria-pressed="true"]{border-color:#ff344b;background:#26131a}.league[aria-pressed="true"]:after{content:'✓';margin-left:auto;font-size:22px}.count{font-weight:700;margin:10px 0;color:#ff7380}.primary{width:100%;padding:16px;border:0;border-radius:14px;background:#e92840;color:white;font-size:17px;font-weight:800}.primary:disabled{opacity:.4}.input{width:100%;padding:14px;margin:6px 0;background:#080e17;color:#fff;border:1px solid #304159;border-radius:10px}.hint{font-size:13px;margin-top:8px}</style></head><body><main><div class="hero"><h1>XSportsX</h1><div class="muted">Nuvio live sports engine • Build ${VERSION}</div></div><div class="panel"><h2>Choose leagues</h2><div id="count" class="count">0 selected</div>${cards}</div><div class="panel"><h2>Xtream source</h2><form method="POST" action="${base}/configure" id="form"><input type="hidden" name="sports" id="sports"><input type="hidden" name="source" value="xtream"><input id="xtream" class="input" name="xtream" placeholder="https://server.example.com" autocomplete="url" required><input id="user" class="input" name="username" placeholder="Username" autocomplete="username" required><input id="pass" class="input" name="password" type="password" placeholder="Password" autocomplete="current-password" required><button id="create" class="primary" type="submit" disabled>Create manifest</button></form><div class="hint muted">Your password is encrypted into your private manifest URL.</div></div></main><script>const buttons=[...document.querySelectorAll('.league')],count=document.getElementById('count'),create=document.getElementById('create'),sports=document.getElementById('sports'),form=document.getElementById('form');function refresh(){const selected=buttons.filter(b=>b.getAttribute('aria-pressed')==='true').map(b=>b.dataset.id);count.textContent=selected.length+' selected';create.disabled=selected.length===0;sports.value=selected.join(',')}buttons.forEach(b=>b.addEventListener('click',()=>{b.setAttribute('aria-pressed',String(b.getAttribute('aria-pressed')!=='true'));refresh()}));form.addEventListener('submit',e=>{refresh();if(!sports.value)e.preventDefault()});refresh();</script></body></html>`;
}
function resultPage(base, manifestUrl) { return `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>XSportsX Manifest Ready</title><style>body{margin:0;background:#070b12;color:#fff;font-family:system-ui;padding:24px}main{max-width:720px;margin:auto;background:#0d1420;border:1px solid #25344a;border-radius:18px;padding:22px}.ok{color:#62e6a5}.url{word-break:break-all;background:#080e17;border:1px solid #304159;padding:14px;border-radius:10px}a{color:#8fc8ff}</style></head><body><main><h1 class="ok">✓ Manifest ready</h1><p>Your private XSportsX configuration was created.</p><p><a href="${manifestUrl}">Open manifest JSON</a></p><div class="url">${manifestUrl}</div><p><a href="${base}/configure">← Back to configuration</a></p></main></body></html>`; }
function readBody(req) { return new Promise((resolve,reject)=>{let body='';req.on('data',chunk=>{body+=chunk;if(body.length>32768){reject(new Error('Request too large'));req.destroy()}});req.on('end',()=>resolve(body));req.on('error',reject)}); }
function tokenFor(url) { const parts=url.pathname.split('/').filter(Boolean); const marker=parts.findIndex(p=>['manifest.json','catalog','meta','stream','play'].includes(p)); if(marker>0)return parts[marker-1]; if(parts.length===1&&!['configure','health','artwork.svg','manifest.json'].includes(parts[0]))return parts[0]; return url.searchParams.get('config')||null; }

async function getJson(url) {
  const r = await fetch(url, { headers: { 'user-agent': 'XSportsX/9.3' }, signal: AbortSignal.timeout(9000) });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}
function cacheGet(key) { const x=CACHE.get(key); if(x && x.expires>Date.now()) return x.value; CACHE.delete(key); return null; }
function cacheSet(key,value,ms=20000) { CACHE.set(key,{value,expires:Date.now()+ms}); return value; }
async function xtream(config, action) {
  const key=`${config.xtream.baseUrl}|${config.xtream.username}|${action}`;
  const cached=cacheGet(key); if(cached) return cached;
  const u=new URL('/player_api.php',config.xtream.baseUrl+'/');
  u.searchParams.set('username',config.xtream.username); u.searchParams.set('password',config.xtream.password); u.searchParams.set('action',action);
  return cacheSet(key, await getJson(u.toString()), 15000);
}
async function getChannels(config) {
  const key=`channels|${config.xtream.baseUrl}|${config.xtream.username}`;
  const cached=cacheGet(key); if(cached) return cached;
  const data=await xtream(config,'get_live_streams');
  return cacheSet(key,Array.isArray(data)?data:[],30000);
}
function norm(s) { return String(s||'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim(); }
function words(s) { return new Set(norm(s).split(/\s+/).filter(w=>w.length>2)); }
function teamNames(event) { const out=[]; for(const c of event.competitions||[]){ for(const cteam of c.competitors||[]){ if(cteam.team?.displayName)out.push(cteam.team.displayName); if(cteam.team?.shortDisplayName)out.push(cteam.team.shortDisplayName); if(cteam.team?.abbreviation)out.push(cteam.team.abbreviation); } } return [...new Set(out)]; }
function channelScore(channel, event, leagueName) {
  const text=norm([channel.name,channel.stream_display_name,channel.tv_archive_duration,channel.category_name].join(' '));
  const cw=words(text); let score=0;
  for(const t of teamNames(event)){const tw=words(t);let hit=0;for(const w of tw)if(cw.has(w))hit++;if(hit)score+=hit*25;if(norm(t) && text.includes(norm(t)))score+=80;}
  const hints=['espn','espn2','espnu','espnews','espn+','fox sports','fs1','fs2','tnt','tbs','tru tv','abc','cbs','nbc','fox','peacock','usa network','univision','telemundo','paramount','tnt sports','altitude','bally','sportsnet','tsn','local'];
  for(const h of hints)if(text.includes(h))score+=4;
  if(text.includes(norm(leagueName)))score+=18;
  return score;
}
function espnConfig(id){const x=LEAGUES.find(l=>l[0]===id);return x?{sport:x[3],league:x[4],name:x[1]}:null;}
async function scoreboard(leagueId) {
  const ec=espnConfig(leagueId); if(!ec) return [];
  const key=`scoreboard|${leagueId}`; const cached=cacheGet(key); if(cached)return cached;
  const url=`https://site.api.espn.com/apis/site/v2/sports/${ec.sport}/${ec.league}/scoreboard?limit=100`;
  try { const data=await getJson(url); return cacheSet(key,Array.isArray(data.events)?data.events:[],15000); } catch { return []; }
}
function eventMeta(leagueId,event,base){
  const comp=event.competitions?.[0]; const competitors=comp?.competitors||[]; const names=competitors.map(c=>c.team?.displayName||c.team?.shortDisplayName).filter(Boolean); const status=comp?.status?.type?.shortDetail||event.status?.type?.shortDetail||''; const date=event.date?new Date(event.date).toISOString():'';
  return {id:`sports:${leagueId}:event:${event.id}`,type:'tv',name:names.length>=2?`${names[0]} vs ${names[1]}`:(event.name||'Live Event'),poster:`${base}/artwork.svg`,posterShape:'landscape',releaseInfo:date?date.slice(0,10):'',description:status?`${status} • ${espnConfig(leagueId)?.name||''}`:`${espnConfig(leagueId)?.name||''} live event`,genres:[espnConfig(leagueId)?.name||'Sports']};
}
async function catalogEvents(config,leagueId,base,search='') {
  const events=await scoreboard(leagueId); const q=norm(search); const filtered=q?events.filter(e=>norm([e.name,e.shortName,...teamNames(e)].join(' ')).includes(q)):events;
  return filtered.slice(0,100).map(e=>eventMeta(leagueId,e,base));
}
async function eventById(leagueId,eventId){ const events=await scoreboard(leagueId); return events.find(e=>String(e.id)===String(eventId))||null; }
async function streamsForEvent(config,leagueId,eventId,base) {
  const event=await eventById(leagueId,eventId); if(!event)return [];
  const channels=await getChannels(config); const leagueName=espnConfig(leagueId)?.name||'';
  const scored=channels.map(c=>({c,s:channelScore(c,event,leagueName)})).filter(x=>x.s>0).sort((a,b)=>b.s-a.s).slice(0,12);
  return scored.map((x,i)=>{const c=x.c;const id=String(c.stream_id||c.num||c.id||'');const url=`${base}/${encrypt({p:config,streamId:id,exp:Date.now()+300000})}/play/${encodeURIComponent(id)}`;return {name:`${c.name||c.stream_display_name||'Channel'}${i===0?' • Best match':''}`,title:`${leagueName} • ${c.name||c.stream_display_name||'Channel'}`,url,behaviorHints:{notWebReady:true}};});
}
function sendCatalog(res,metas){ return json(res,200,{metas}); }

const server=http.createServer(async(req,res)=>{
  headers(res);
  if(req.method==='OPTIONS'){res.statusCode=204;return res.end();}
  const url=new URL(req.url||'/',`http://${req.headers.host||'localhost'}`);
  const forwarded=String(req.headers['x-forwarded-proto']||'').split(',')[0].trim().toLowerCase();
  const scheme=forwarded==='https'?'https':url.protocol.replace(':','');
  const base=`${scheme}://${url.host}`;

  if(req.method==='GET'&&(url.pathname==='/'||url.pathname==='/configure')){headers(res,'text/html; charset=utf-8');return res.end(configPage(base));}
  if(req.method==='GET'&&url.pathname==='/health')return json(res,200,{ok:true,version:VERSION,scheme});
  if(req.method==='GET'&&url.pathname==='/artwork.svg')return artwork(res);

  if(req.method==='POST'&&url.pathname==='/configure'){
    try{
      const contentType=String(req.headers['content-type']||'');let input;
      if(contentType.includes('application/x-www-form-urlencoded')){const body=await readBody(req);const form=new URLSearchParams(body);input={source:form.get('source'),sports:String(form.get('sports')||'').split(',').filter(Boolean),xtream:{baseUrl:form.get('xtream'),username:form.get('username'),password:form.get('password')}};}else{input=JSON.parse(await readBody(req));}
      const sports=[...new Set(Array.isArray(input.sports)?input.sports.map(String).filter(id=>VALID.has(id)):[])];
      if(!sports.length)return json(res,400,{error:'Select at least one league.'});
      const baseUrl=normalizeXtreamUrl(input.xtream?.baseUrl),username=String(input.xtream?.username||'').trim(),password=String(input.xtream?.password||'');
      if(!baseUrl||!username||!password)return json(res,400,{error:'Enter the Xtream server URL, username, and password.'});
      const config={source:'xtream',sports,xtream:{baseUrl,username,password}};
      const manifestUrl=`${base}/${encrypt(config)}/manifest.json`;
      if(contentType.includes('application/x-www-form-urlencoded')){headers(res,'text/html; charset=utf-8');return res.end(resultPage(base,manifestUrl));}
      return json(res,200,{version:VERSION,manifestUrl});
    }catch(e){return json(res,400,{error:e.message||'Invalid configuration.'});}
  }

  const token=tokenFor(url);
  let config=decrypt(token);
  let playConfig=null;
  if(url.pathname.includes('/play/')){const decoded=decrypt(token);if(decoded?.p){playConfig=decoded;config=decoded.p;}}
  if(!config||!Array.isArray(config.sports)||!config.sports.length)return json(res,404,{error:'Invalid or expired XSportsX configuration.'});

  if(req.method==='GET'&&(url.pathname.endsWith('/manifest.json')||url.pathname===`/${token}`))return json(res,200,manifest(base,config));

  try {
    if(req.method==='GET'&&url.pathname.includes('/catalog/')){
      const parts=url.pathname.split('/').filter(Boolean); const i=parts.indexOf('catalog'); const catalogId=String(parts[i+2]||'').replace(/\.json$/i,''); const leagueId=catalogId.replace(/^sports:/,'');
      if(!VALID.has(leagueId)||!config.sports.includes(leagueId))return sendCatalog(res,[]);
      const metas=await catalogEvents(config,leagueId,base,url.searchParams.get('search')||''); return sendCatalog(res,metas);
    }
    if(req.method==='GET'&&url.pathname.includes('/meta/')){
      const parts=url.pathname.split('/').filter(Boolean); const i=parts.indexOf('meta'); const raw=String(parts[i+2]||'').replace(/\.json$/i,''); const m=raw.match(/^sports:([^:]+):event:(.+)$/); if(!m)return json(res,200,{meta:null}); const event=await eventById(m[1],m[2]); if(!event)return json(res,200,{meta:null}); return json(res,200,{meta:eventMeta(m[1],event,base)});
    }
    if(req.method==='GET'&&url.pathname.includes('/stream/')){
      const parts=url.pathname.split('/').filter(Boolean); const i=parts.indexOf('stream'); const raw=String(parts[i+2]||'').replace(/\.json$/i,''); const m=raw.match(/^sports:([^:]+):event:(.+)$/); if(!m)return json(res,200,{streams:[]}); return json(res,200,{streams:await streamsForEvent(config,m[1],m[2],base)});
    }
    if(req.method==='GET'&&url.pathname.includes('/play/')){
      if(!playConfig || Number(playConfig.exp||0)<Date.now())return json(res,410,{error:'Playback link expired. Refresh streams.'});
      const channels=await getChannels(config); const c=channels.find(x=>String(x.stream_id||x.num||x.id||'')===String(playConfig.streamId)); if(!c)return json(res,404,{error:'Channel not found.'});
      const u=new URL('/live/'+encodeURIComponent(config.xtream.username)+'/'+encodeURIComponent(config.xtream.password)+'/'+encodeURIComponent(String(c.stream_id||c.num||c.id))+'.ts',config.xtream.baseUrl+'/'); res.statusCode=302;res.setHeader('location',u.toString());res.setHeader('cache-control','no-store');return res.end();
    }
  } catch(e) { return json(res,502,{error:'Source lookup failed',detail:String(e.message||e)}); }
  return json(res,404,{error:'Not found'});
});
server.listen(PORT,'0.0.0.0',()=>console.log(`XSportsX ${VERSION} listening on ${PORT}`));
