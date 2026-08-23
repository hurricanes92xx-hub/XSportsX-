const http = require('http');
const crypto = require('crypto');
const { URL } = require('url');

const publicPort = Number(process.env.PORT || 10000);
const internalPort = publicPort + 1;
process.env.PORT = String(internalPort);
require('./server.js');

const RESOURCES = new Set(['manifest.json', 'catalog', 'meta', 'stream']);
const PUBLIC = new Set(['configure', 'health', 'xtream-health', 'artwork', 'qr']);
const SECRET = process.env.XSPORTSX_CONFIG_SECRET || 'change-this-xsportsx-secret-in-render';
const KEY = crypto.createHash('sha256').update(SECRET).digest();
const BUILD_VERSION = '7.6.1';

const LEAGUES = {
  nfl:['NFL','🏈'], ncaaf:['NCAA Football','🏈'], nba:['NBA','🏀'], wnba:['WNBA','🏀'],
  ncaab:['NCAA Basketball','🏀'], mlb:['MLB','⚾'], nhl:['NHL','🏒'], mls:['MLS','⚽'],
  epl:['Premier League','⚽'], ucl:['UEFA Champions League','⚽'], laliga:['LaLiga','⚽'],
  seriea:['Serie A','⚽'], bundesliga:['Bundesliga','⚽'], ligue1:['Ligue 1','⚽'],
  ufc:['UFC','🥊'], boxing:['Boxing','🥊']
};

const ALIASES = {
  nfl:['nfl'], ncaaf:['ncaaf','ncaafb','ncaa football','college football','college-football'],
  nba:['nba'], wnba:['wnba'], ncaab:['ncaab','ncaamb','ncaa basketball','college basketball','mens-college-basketball'],
  mlb:['mlb'], nhl:['nhl'], mls:['mls'], epl:['epl','premier league','english premier league'],
  ucl:['ucl','uefa champions league','champions league'], laliga:['laliga','la liga'],
  seriea:['seriea','serie a'], bundesliga:['bundesliga'], ligue1:['ligue1','ligue 1'],
  ufc:['ufc','mma'], boxing:['boxing','box']
};

function decryptConfig(token) {
  try {
    const [ivS, tagS, bodyS] = String(token || '').split('.');
    if (!ivS || !tagS || !bodyS) return null;
    const d = crypto.createDecipheriv('aes-256-gcm', KEY, Buffer.from(ivS, 'base64url'));
    d.setAuthTag(Buffer.from(tagS, 'base64url'));
    return JSON.parse(Buffer.concat([d.update(Buffer.from(bodyS, 'base64url')), d.final()]).toString('utf8'));
  } catch { return null; }
}

function canonical(v) {
  const x = String(v || '').trim().toLowerCase();
  for (const [id, aliases] of Object.entries(ALIASES)) if (aliases.includes(x)) return id;
  return null;
}

function selectedSports(token) {
  const c = decryptConfig(token);
  if (!c) return null;
  const raw = Array.isArray(c.sports) ? c.sports : [];
  if (!raw.length) return new Set(Object.keys(LEAGUES));
  return new Set(raw.map(canonical).filter(Boolean));
}

function tokenFrom(raw) {
  const u = new URL(raw || '/', 'http://local');
  let parts = u.pathname.split('/').filter(Boolean);
  if (parts[0] === 'v527') parts = parts.slice(1);
  const i = parts.findIndex(p => RESOURCES.has(p) || p.startsWith('catalog') || p.startsWith('meta') || p.startsWith('stream'));
  if (i > 0) return parts[i - 1];
  if (parts.length === 1 && !PUBLIC.has(parts[0]) && !parts[0].endsWith('.json')) return parts[0];
  return u.searchParams.get('config') || '';
}

function rewrite(raw) {
  const u = new URL(raw || '/', 'http://local');
  let parts = u.pathname.split('/').filter(Boolean);
  if (parts[0] === 'v527') parts = parts.slice(1);
  const i = parts.findIndex(p => RESOURCES.has(p) || p.startsWith('catalog') || p.startsWith('meta') || p.startsWith('stream'));
  if (i < 0) {
    if (parts.length === 1 && !PUBLIC.has(parts[0]) && !parts[0].endsWith('.json')) {
      u.pathname = '/manifest.json';
      u.searchParams.set('config', parts[0]);
    }
    return u.pathname + (u.search || '');
  }
  const before = parts.slice(0, i);
  u.pathname = '/' + parts.slice(i).join('/');
  if (before.length) u.searchParams.set('config', before[before.length - 1]);
  return u.pathname + (u.search || '');
}

function privateManifest(base, token) {
  const selected = selectedSports(token);
  const catalogs = selected ? [...selected].filter(id => LEAGUES[id]).map(id => ({
    type:'tv', id, name:`${LEAGUES[id][1]} ${LEAGUES[id][0].toUpperCase()}`, extra:[], showInHome:true
  })) : [];
  const id = `community.xsportsx.${crypto.createHash('sha256').update(String(token)).digest('hex').slice(0,20)}`;
  return {
    id, version:BUILD_VERSION, name:'XSportsX',
    description:'Premium live sports for Nuvio using your own Xtream or M3U source.',
    resources:[{name:'catalog',types:['tv']},{name:'meta',types:['tv']},{name:'stream',types:['tv']}],
    types:['tv'], idPrefixes:['sport:','xtream:'], catalogs,
    behaviorHints:{configurable:false,configurationRequired:false}, logo:`${base}/artwork/other.svg`
  };
}

function setupPageHtml(body) {
  body = body.replace(/XSportsX BUILD 7\.2\.0 • LIVE/g, `XSportsX BUILD ${BUILD_VERSION} • LIVE`);
  const marker = `<div style="position:sticky;top:0;z-index:9999;margin:0 0 18px;padding:12px 16px;border:1px solid #ff2438;border-radius:14px;background:#0a101b;color:#fff;font:800 14px Inter,system-ui,sans-serif"><span style="color:#ff2438">XSportsX</span> ${BUILD_VERSION} • PRIVATE SPORTS CONNECTION BUILDER • Xtream / M3U • League Selection • Device Sync</div>`;
  return body.includes('</body>') ? body.replace('</body>', `${marker}</body>`) : body;
}

const proxy = http.createServer((req, res) => {
  try {
    const token = tokenFrom(req.url);
    const path = rewrite(req.url);
    const parsedPath = new URL(path, 'http://local').pathname;
    const base = `${String(req.headers['x-forwarded-proto'] || 'https').split(',')[0]}://${req.headers.host || 'localhost'}`;

    if (req.method === 'GET' && parsedPath === '/manifest.json' && token) {
      const selected = selectedSports(token);
      const body = JSON.stringify(privateManifest(base, token));
      res.writeHead(200, {
        'content-type':'application/json; charset=utf-8', 'content-length':String(Buffer.byteLength(body)),
        'cache-control':'no-store, no-cache, must-revalidate, proxy-revalidate', 'pragma':'no-cache', 'expires':'0',
        'x-xsportsx-build':BUILD_VERSION, 'x-xsportsx-configured':selected?'true':'false',
        'x-xsportsx-selected-leagues':selected?[...selected].join(','):'configuration-unreadable'
      });
      return res.end(body);
    }

    const upstream = http.request({
      hostname:'127.0.0.1', port:internalPort, path, method:req.method,
      headers:{...req.headers, host:`127.0.0.1:${internalPort}`}
    }, response => {
      const ct = String(response.headers['content-type'] || '');
      const setup = parsedPath === '/configure' && ct.includes('text/html');
      const catalog = Boolean(token) && parsedPath.startsWith('/catalog/');
      if (!setup && !catalog) {
        const h={...response.headers,'x-xsportsx-build':BUILD_VERSION};
        if(parsedPath==='/configure'){h['cache-control']='no-store, no-cache, must-revalidate, proxy-revalidate';h['pragma']='no-cache';}
        res.writeHead(response.statusCode||502,h); return response.pipe(res);
      }
      const chunks=[]; response.on('data',c=>chunks.push(c)); response.on('end',()=>{
        try {
          if(setup){
            const out=Buffer.from(setupPageHtml(Buffer.concat(chunks).toString('utf8')));
            const h={...response.headers,'content-length':String(out.length),'cache-control':'no-store, no-cache, must-revalidate, proxy-revalidate','pragma':'no-cache','x-xsportsx-build':BUILD_VERSION};
            delete h['transfer-encoding']; res.writeHead(response.statusCode||200,h); return res.end(out);
          }
          const selected=selectedSports(token);
          const id=(parsedPath.match(/^\/catalog\/tv\/([^./]+)\.json$/)||[])[1];
          if(selected && id && LEAGUES[id] && !selected.has(id)){
            const out=Buffer.from(JSON.stringify({metas:[]}));
            res.writeHead(200,{'content-type':'application/json','content-length':String(out.length),'cache-control':'no-store','x-xsportsx-build':BUILD_VERSION,'x-xsportsx-selected-leagues':[...selected].join(',')});
            return res.end(out);
          }
          const out=Buffer.concat(chunks); const h={...response.headers,'x-xsportsx-build':BUILD_VERSION,'cache-control':'no-store, no-cache, must-revalidate, proxy-revalidate'};
          delete h['transfer-encoding']; res.writeHead(response.statusCode||502,h); res.end(out);
        } catch {res.writeHead(response.statusCode||502,response.headers);res.end(Buffer.concat(chunks));}
      });
    });
    upstream.on('error',e=>{res.statusCode=502;res.end(`XSportsX bootstrap error: ${e.message}`);});
    req.pipe(upstream);
  } catch(e){res.statusCode=400;res.end(`XSportsX bootstrap request error: ${e.message}`);}
});

proxy.listen(publicPort,'0.0.0.0',()=>console.log(`XSportsX bootstrap ${BUILD_VERSION} listening on ${publicPort}; app on ${internalPort}`));
