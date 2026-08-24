const http = require('http');
const crypto = require('crypto');
const { URL } = require('url');

const PORT = Number(process.env.PORT || 10000);
const SECRET = process.env.XSPORTSX_CONFIG_SECRET || 'change-this-in-render';
const KEY = crypto.createHash('sha256').update(SECRET).digest();
const VERSION = '9.2.0';

const LEAGUES = [
  ['nfl', 'NFL', '🏈'], ['ncaaf', 'NCAA Football', '🏈'],
  ['nba', 'NBA', '🏀'], ['wnba', 'WNBA', '🏀'],
  ['ncaab', 'NCAA Basketball', '🏀'], ['mlb', 'MLB', '⚾'],
  ['nhl', 'NHL', '🏒'], ['mls', 'MLS', '⚽'],
  ['epl', 'Premier League', '⚽'], ['ucl', 'UEFA Champions League', '⚽'],
  ['laliga', 'LaLiga', '⚽'], ['seriea', 'Serie A', '⚽'],
  ['bundesliga', 'Bundesliga', '⚽'], ['ligue1', 'Ligue 1', '⚽'],
  ['ufc', 'UFC', '🥊'], ['boxing', 'Boxing', '🥊']
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
    description: 'Live sports from your own Xtream source.', types: ['tv'],
    resources: [
      { name: 'catalog', types: ['tv'] },
      { name: 'meta', types: ['tv'], idPrefixes: ['sports:'] },
      { name: 'stream', types: ['tv'], idPrefixes: ['sports:'] }
    ],
    catalogs: config.sports.map(id => { const l = LEAGUES.find(x => x[0] === id); return { type: 'tv', id: `sports:${id}`, name: `${l[2]} ${l[1]}` }; }),
    behaviorHints: { configurable: false, configurationRequired: false }, logo: `${base}/artwork.svg`
  };
}
function artwork(res) {
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512"><rect width="100%" height="100%" fill="#070b12"/><text x="50%" y="48%" text-anchor="middle" fill="white" font-family="Arial" font-size="64" font-weight="700">XSPORTSX</text><text x="50%" y="58%" text-anchor="middle" fill="#ff344b" font-family="Arial" font-size="28">LIVE SPORTS</text></svg>';
  headers(res, 'image/svg+xml'); res.setHeader('cache-control', 'public,max-age=86400'); res.end(svg);
}
function esc(value) { return String(value).replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c])); }
function configPage(base) {
  const cards = LEAGUES.map(([id, name, emoji]) => `<button class="league" type="button" data-id="${id}" aria-pressed="false"><span>${emoji}</span><strong>${name}</strong></button>`).join('');
  return `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"><title>XSportsX 9.2</title><style>*{box-sizing:border-box}body{margin:0;background:#070b12;color:#fff;font-family:system-ui,-apple-system,Segoe UI,sans-serif}main{max-width:720px;margin:auto;padding:20px}.hero,.panel{background:#0d1420;border:1px solid #25344a;border-radius:18px;padding:20px;margin-bottom:16px}.hero h1{margin:0 0 4px;font-size:32px}.muted{color:#91a0b5}.league{width:100%;display:flex;align-items:center;gap:14px;text-align:left;padding:15px;margin:7px 0;border-radius:14px;border:1px solid #2a3a50;background:#121b29;color:#fff;font-size:17px;cursor:pointer;touch-action:manipulation}.league span{font-size:24px}.league[aria-pressed="true"]{border-color:#ff344b;background:#26131a}.league[aria-pressed="true"]:after{content:'✓';margin-left:auto;font-size:22px}.count{font-weight:700;margin:10px 0;color:#ff7380}.primary{width:100%;padding:16px;border:0;border-radius:14px;background:#e92840;color:white;font-size:17px;font-weight:800}.primary:disabled{opacity:.4}.input{width:100%;padding:14px;margin:6px 0;background:#080e17;color:#fff;border:1px solid #304159;border-radius:10px}.hint{font-size:13px;margin-top:8px}</style></head><body><main><div class="hero"><h1>XSportsX</h1><div class="muted">Nuvio live sports engine • Build ${VERSION}</div></div><div class="panel"><h2>Choose leagues</h2><div id="count" class="count">0 selected</div>${cards}</div><div class="panel"><h2>Xtream source</h2><form method="POST" action="${base}/configure" id="form"><input type="hidden" name="sports" id="sports"><input type="hidden" name="source" value="xtream"><input id="xtream" class="input" name="xtream" placeholder="https://server.example.com" autocomplete="url" required><input id="user" class="input" name="username" placeholder="Username" autocomplete="username" required><input id="pass" class="input" name="password" type="password" placeholder="Password" autocomplete="current-password" required><button id="create" class="primary" type="submit" disabled>Create manifest</button></form><div class="hint muted">Your password is encrypted into your private manifest URL.</div></div></main><script>const buttons=[...document.querySelectorAll('.league')],count=document.getElementById('count'),create=document.getElementById('create'),sports=document.getElementById('sports'),form=document.getElementById('form');function refresh(){const selected=buttons.filter(b=>b.getAttribute('aria-pressed')==='true').map(b=>b.dataset.id);count.textContent=selected.length+' selected';create.disabled=selected.length===0;sports.value=selected.join(',')}buttons.forEach(b=>b.addEventListener('click',()=>{b.setAttribute('aria-pressed',String(b.getAttribute('aria-pressed')!=='true'));refresh()}));form.addEventListener('submit',e=>{refresh();if(!sports.value)e.preventDefault()});refresh();</script></body></html>`;
}
function resultPage(base, manifestUrl) { return `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>XSportsX Manifest Ready</title><style>body{margin:0;background:#070b12;color:#fff;font-family:system-ui;padding:24px}main{max-width:720px;margin:auto;background:#0d1420;border:1px solid #25344a;border-radius:18px;padding:22px}.ok{color:#62e6a5}.url{word-break:break-all;background:#080e17;border:1px solid #304159;padding:14px;border-radius:10px}a{color:#8fc8ff}</style></head><body><main><h1 class="ok">✓ Manifest ready</h1><p>Your private XSportsX configuration was created.</p><p><a href="${esc(manifestUrl)}">Open manifest JSON</a></p><div class="url">${esc(manifestUrl)}</div><p><a href="${base}/configure">← Back to configuration</a></p></main></body></html>`; }
function readBody(req) { return new Promise((resolve,reject)=>{let body='';req.on('data',chunk=>{body+=chunk;if(body.length>32768){reject(new Error('Request too large'));req.destroy()}});req.on('end',()=>resolve(body));req.on('error',reject)}); }
function tokenFor(url) { const parts=url.pathname.split('/').filter(Boolean); const marker=parts.findIndex(p=>p==='manifest.json'||p==='catalog'||p==='meta'||p==='stream'); if(marker>0)return parts[marker-1]; if(parts.length===1&&!['configure','health','artwork.svg','manifest.json'].includes(parts[0]))return parts[0]; return url.searchParams.get('config')||null; }
function sendCatalog(res,config,catalogId){const id=String(catalogId||'').replace(/^sports:/,'');if(!VALID.has(id)||!config.sports.includes(id))return json(res,200,{metas:[]});return json(res,200,{metas:[]});}

const server=http.createServer(async(req,res)=>{
  headers(res);
  if(req.method==='OPTIONS'){res.statusCode=204;return res.end();}
  const url=new URL(req.url||'/',`http://${req.headers.host||'localhost'}`);
  // Render terminates TLS at the proxy. Use the forwarded HTTPS scheme so forms
  // and generated manifest URLs never downgrade to plain HTTP.
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
  const token=tokenFor(url),config=decrypt(token);
  if(!config||!Array.isArray(config.sports)||!config.sports.length)return json(res,404,{error:'Invalid or expired XSportsX configuration.'});
  if(req.method==='GET'&&(url.pathname.endsWith('/manifest.json')||url.pathname===`/${token}`))return json(res,200,manifest(base,config));
  if(req.method==='GET'&&url.pathname.includes('/catalog/')){const parts=url.pathname.split('/').filter(Boolean),i=parts.indexOf('catalog');return sendCatalog(res,config,parts[i+2]||'');}
  if(req.method==='GET'&&(url.pathname.includes('/meta/')||url.pathname.includes('/stream/')))return json(res,200,{metas:[],streams:[]});
  return json(res,404,{error:'Not found'});
});
server.listen(PORT,'0.0.0.0',()=>console.log(`XSportsX ${VERSION} listening on ${PORT}`));
