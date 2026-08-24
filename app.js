const http = require('http');
const crypto = require('crypto');
const { URL } = require('url');

const PORT = Number(process.env.PORT || 10000);
const SECRET = process.env.XSPORTSX_CONFIG_SECRET || 'change-this-in-render';
const KEY = crypto.createHash('sha256').update(SECRET).digest();
const VERSION = '1.0.1';

const LEAGUES = [
  ['nfl', 'NFL', '🏈'], ['ncaaf', 'NCAA Football', '🏈'],
  ['nba', 'NBA', '🏀'], ['ncaab', 'NCAA Basketball', '🏀'],
  ['mlb', 'MLB', '⚾'], ['nhl', 'NHL', '🏒'],
  ['ufc', 'UFC', '🥊'], ['boxing', 'Boxing', '🥊']
];
const VALID = new Set(LEAGUES.map(([id]) => id));

function json(res, status, body) {
  const text = JSON.stringify(body);
  res.writeHead(status, {'content-type':'application/json; charset=utf-8','cache-control':'no-store','x-xsportsx-version':VERSION,'content-length':Buffer.byteLength(text)});
  res.end(text);
}
function encrypt(value) {
  const iv=crypto.randomBytes(12), cipher=crypto.createCipheriv('aes-256-gcm',KEY,iv);
  const body=Buffer.concat([cipher.update(JSON.stringify(value),'utf8'),cipher.final()]);
  return [iv,cipher.getAuthTag(),body].map(b=>b.toString('base64url')).join('.');
}
function decrypt(token) {
  try { const [iv,tag,body]=String(token||'').split('.'); if(!iv||!tag||!body)return null;
    const decipher=crypto.createDecipheriv('aes-256-gcm',KEY,Buffer.from(iv,'base64url'));decipher.setAuthTag(Buffer.from(tag,'base64url'));
    return JSON.parse(Buffer.concat([decipher.update(Buffer.from(body,'base64url')),decipher.final()]).toString('utf8'));
  } catch { return null; }
}
function page(base) {
  const groups=[['Football',['nfl','ncaaf']],['Basketball',['nba','ncaab']],['Baseball / Hockey',['mlb','nhl']],['Combat',['ufc','boxing']]];
  const cards=groups.map(([title,ids])=>`<section class="group"><h2>${title}</h2>${ids.map(id=>{const l=LEAGUES.find(x=>x[0]===id);return `<button class="league" type="button" data-id="${id}" aria-pressed="false"><span>${l[2]}</span><strong>${l[1]}</strong></button>`;}).join('')}</section>`).join('');
  return `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"><title>XSportsX</title><style>*{box-sizing:border-box}body{margin:0;background:#070b12;color:#fff;font-family:system-ui,-apple-system,Segoe UI,sans-serif}main{max-width:720px;margin:auto;padding:20px}.hero,.panel{background:#0d1420;border:1px solid #25344a;border-radius:18px;padding:20px;margin-bottom:16px}.hero h1{margin:0 0 5px;font-size:32px}.muted{color:#91a0b5}.group{margin-top:18px}.league{width:100%;display:flex;align-items:center;gap:14px;text-align:left;padding:16px;margin:8px 0;border-radius:14px;border:1px solid #2a3a50;background:#121b29;color:#fff;font-size:17px;cursor:pointer;touch-action:manipulation}.league span{font-size:25px}.league[aria-pressed="true"]{border-color:#ff344b;background:#26131a}.league[aria-pressed="true"]:after{content:'✓';margin-left:auto;font-size:22px}.count{font-weight:700;margin:10px 0;color:#ff7380}.primary{width:100%;padding:16px;border:0;border-radius:14px;background:#e92840;color:white;font-size:17px;font-weight:800}.primary:disabled{opacity:.4}.result{word-break:break-all;margin-top:15px}.result a{color:#8fc8ff}.input{width:100%;padding:14px;margin:6px 0;background:#080e17;color:#fff;border:1px solid #304159;border-radius:10px}</style></head><body><main><div class="hero"><h1>XSportsX</h1><div class="muted">Simple sports setup • v${VERSION}</div></div><div class="panel"><h2>Choose your leagues</h2><div id="count" class="count">0 selected</div>${cards}</div><div class="panel"><h2>IPTV source</h2><input id="xtream" class="input" placeholder="Xtream server URL"><input id="user" class="input" placeholder="Username"><input id="pass" class="input" type="password" placeholder="Password"><button id="create" class="primary" disabled>Create connection</button><div id="result" class="result muted"></div></div></main><script>const buttons=[...document.querySelectorAll('.league')],count=document.getElementById('count'),create=document.getElementById('create');function refresh(){const n=buttons.filter(b=>b.getAttribute('aria-pressed')==='true').length;count.textContent=n+' selected';create.disabled=n===0}buttons.forEach(b=>b.addEventListener('click',()=>{b.setAttribute('aria-pressed',String(b.getAttribute('aria-pressed')!=='true'));refresh()}));create.addEventListener('click',async()=>{const sports=buttons.filter(b=>b.getAttribute('aria-pressed')==='true').map(b=>b.dataset.id),result=document.getElementById('result');result.textContent='Creating connection…';try{const r=await fetch('${base}/configure',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({sports,source:'xtream',xtream:{baseUrl:document.getElementById('xtream').value.trim(),username:document.getElementById('user').value,password:document.getElementById('pass').value}})}),d=await r.json();if(!r.ok)throw Error(d.error||'Unable to create connection');result.innerHTML='<b>Connection created.</b><br><br><a href="'+d.manifestUrl+'">'+d.manifestUrl+'</a>'}catch(e){result.textContent=e.message}});refresh();</script></body></html>`;
}
function manifest(base,config){return{id:'community.xsportsx.'+crypto.createHash('sha256').update(JSON.stringify(config)).digest('hex').slice(0,16),version:VERSION,name:'XSportsX',description:'XSportsX sports addon using your own IPTV source.',types:['tv'],resources:[{name:'catalog',types:['tv'],idPrefixes:['sports:']},{name:'meta',types:['tv'],idPrefixes:['sports:']},{name:'stream',types:['tv'],idPrefixes:['sports:']}],catalogs:config.sports.map(id=>{const l=LEAGUES.find(x=>x[0]===id);return{type:'tv',id:`sports:${id}`,name:`${l[2]} ${l[1]}`};}),behaviorHints:{configurable:false,configurationRequired:false},logo:`${base}/artwork.svg`};}
function artwork(res){const svg='<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512"><rect width="100%" height="100%" fill="#070b12"/><text x="50%" y="48%" text-anchor="middle" fill="white" font-family="Arial" font-size="64" font-weight="700">XSPORTSX</text><text x="50%" y="58%" text-anchor="middle" fill="#ff344b" font-family="Arial" font-size="28">LIVE SPORTS</text></svg>';res.writeHead(200,{'content-type':'image/svg+xml','cache-control':'public,max-age=86400'});res.end(svg);}
function tokenFrom(pathname){const p=pathname.split('/').filter(Boolean);return p[0]==='manifest.json'?null:(p[0]||null);}
const server=http.createServer((req,res)=>{const url=new URL(req.url||'/',`http://${req.headers.host||'localhost'}`),base=`${url.protocol}//${url.host}`;
  if(req.method==='GET'&&(url.pathname==='/'||url.pathname==='/configure')){const body=page(base);res.writeHead(200,{'content-type':'text/html; charset=utf-8','cache-control':'no-store','x-xsportsx-version':VERSION});return res.end(body);}
  if(req.method==='GET'&&url.pathname==='/health')return json(res,200,{ok:true,version:VERSION});
  if(req.method==='POST'&&url.pathname==='/configure'){let body='';req.on('data',c=>{body+=c;if(body.length>32768)req.destroy()});req.on('end',()=>{try{const input=JSON.parse(body),sports=[...new Set(Array.isArray(input.sports)?input.sports.map(String).filter(id=>VALID.has(id)):[])];if(!sports.length)return json(res,400,{error:'Select at least one league.'});const config={source:'xtream',sports,xtream:{baseUrl:String(input.xtream?.baseUrl||'').replace(/\/$/,''),username:String(input.xtream?.username||''),password:String(input.xtream?.password||'')}};return json(res,200,{version:VERSION,manifestUrl:`${base}/${encrypt(config)}/manifest.json`});}catch{return json(res,400,{error:'Invalid configuration.'})}});return;}
  if(req.method==='GET'&&url.pathname==='/artwork.svg')return artwork(res);
  const token=tokenFrom(url.pathname);if(req.method==='GET'&&token&&url.pathname.endsWith('/manifest.json')){const config=decrypt(token);if(!config||!Array.isArray(config.sports)||!config.sports.length)return json(res,404,{error:'Invalid configuration.'});return json(res,200,manifest(base,config));}
  res.statusCode=404;res.end('Not found');
});
server.listen(PORT,'0.0.0.0',()=>console.log(`XSportsX ${VERSION} listening on ${PORT}`));
