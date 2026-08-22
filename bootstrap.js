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
const BUILD_VERSION = '7.3.1';

const SPORT_ALIASES = {
  nfl: ['nfl', 'football', 'american football'],
  ncaaf: ['ncaaf', 'ncaafb', 'ncaa football', 'college football', 'college-football'],
  nba: ['nba'], wnba: ['wnba'],
  ncaab: ['ncaab', 'ncaamb', 'ncaa basketball', 'college basketball', 'mens-college-basketball'],
  mlb: ['mlb'], nhl: ['nhl'], mls: ['mls'],
  epl: ['epl', 'premier league', 'english premier league'],
  ucl: ['ucl', 'uefa champions league', 'champions league'],
  laliga: ['laliga', 'la liga'], seriea: ['seriea', 'serie a'],
  bundesliga: ['bundesliga'], ligue1: ['ligue1', 'ligue 1'],
  ufc: ['ufc', 'mma'], boxing: ['boxing', 'box']
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

function canonicalSport(value) {
  const raw = String(value || '').trim().toLowerCase();
  for (const [id, aliases] of Object.entries(SPORT_ALIASES)) if (aliases.includes(raw)) return id;
  return raw;
}

function tokenFrom(raw) {
  const parts = new URL(raw || '/', 'http://local').pathname.split('/').filter(Boolean);
  if (!parts.length) return '';
  if (parts[0] === 'v527') return parts[1] || '';
  const i = parts.findIndex(p => RESOURCES.has(p) || p.startsWith('catalog') || p.startsWith('meta') || p.startsWith('stream'));
  if (i > 0) return parts[i - 1];
  if (parts.length === 1 && !PUBLIC.has(parts[0]) && !parts[0].endsWith('.json')) return parts[0];
  return '';
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

function selectedSports(token) {
  const c = decryptConfig(token);
  if (!c) return null;
  const raw = Array.isArray(c.sports) ? c.sports : [];
  if (!raw.length) return new Set(Object.keys(SPORT_ALIASES));
  return new Set(raw.map(canonicalSport).filter(Boolean));
}

function isSelected(selected, id) {
  return !selected || selected.has(canonicalSport(id));
}

function filterPayload(body, token, path) {
  const selected = selectedSports(token);
  if (!body || typeof body !== 'object') return body;

  if (path === '/manifest.json') {
    body.version = BUILD_VERSION;
    body.id = `community.xsportsx.${crypto.createHash('sha256').update(String(token)).digest('hex').slice(0, 16)}`;
    if (Array.isArray(body.catalogs)) {
      // A private connection contains ONLY the leagues selected in its token.
      // Aggregate catalogs are deliberately removed because they can reintroduce
      // events from leagues the user did not select.
      body.catalogs = selected ? body.catalogs.filter(c => isSelected(selected, c.id)) : [];
      body.catalogs = body.catalogs.map(c => ({ ...c, showInHome: true }));
    }
  }

  if (Array.isArray(body.metas) && selected) {
    body.metas = body.metas.filter(meta => {
      const id = String(meta?.id || '');
      if (id.startsWith('sport:')) return isSelected(selected, id.split(':')[1]);
      return true;
    });
  }
  return body;
}

function setupPageHtml(body) {
  const marker = `<div style="position:sticky;top:0;z-index:9999;margin:0 0 18px;padding:12px 16px;border:1px solid #ff2438;border-radius:14px;background:#0a101b;color:#fff;font:800 14px Inter,system-ui,sans-serif;box-shadow:0 10px 30px rgba(0,0,0,.35)"><span style="color:#ff2438">XSportsX</span> ${BUILD_VERSION} &nbsp;•&nbsp; PRIVATE SPORTS CONNECTION BUILDER &nbsp;•&nbsp; Xtream / M3U &nbsp;•&nbsp; League Selection &nbsp;•&nbsp; Device Sync</div>`;
  return body.includes('</body>') ? body.replace('</body>', `${marker}</body>`) : body;
}

const proxy = http.createServer((req, res) => {
  try {
    const token = tokenFrom(req.url);
    const path = rewrite(req.url);
    const upstream = http.request({
      hostname: '127.0.0.1', port: internalPort, path, method: req.method,
      headers: { ...req.headers, host: `127.0.0.1:${internalPort}` }
    }, response => {
      const ct = String(response.headers['content-type'] || '');
      const jsonFilter = Boolean(token) && ct.includes('application/json') && (path === '/manifest.json' || path.startsWith('/catalog/'));
      const setupFilter = path === '/configure' && ct.includes('text/html');
      if (!jsonFilter && !setupFilter) {
        const h = { ...response.headers, 'x-xsportsx-build': BUILD_VERSION };
        if (path === '/configure') {
          h['cache-control'] = 'no-store, no-cache, must-revalidate, proxy-revalidate';
          h['pragma'] = 'no-cache';
        }
        res.writeHead(response.statusCode || 502, h);
        return response.pipe(res);
      }
      const chunks = [];
      response.on('data', c => chunks.push(c));
      response.on('end', () => {
        try {
          if (setupFilter) {
            const out = Buffer.from(setupPageHtml(Buffer.concat(chunks).toString('utf8')));
            const h = { ...response.headers, 'content-length': String(out.length), 'cache-control': 'no-store, no-cache, must-revalidate, proxy-revalidate', 'pragma': 'no-cache', 'x-xsportsx-build': BUILD_VERSION };
            delete h['transfer-encoding']; res.writeHead(response.statusCode || 200, h); return res.end(out);
          }
          const body = filterPayload(JSON.parse(Buffer.concat(chunks).toString('utf8')), token, path);
          const out = Buffer.from(JSON.stringify(body));
          const selected = selectedSports(token);
          const selectedHeader = selected ? [...selected].join(',') : 'configuration-unreadable';
          const h = {
            ...response.headers, 'content-length': String(out.length),
            'cache-control': 'no-store, no-cache, must-revalidate, proxy-revalidate',
            'pragma': 'no-cache', 'expires': '0', 'x-xsportsx-build': BUILD_VERSION,
            'x-xsportsx-selected-leagues': selectedHeader,
            'x-xsportsx-configured': selected ? 'true' : 'false'
          };
          delete h['transfer-encoding']; res.writeHead(response.statusCode || 502, h); res.end(out);
        } catch {
          res.writeHead(response.statusCode || 502, response.headers); res.end(Buffer.concat(chunks));
        }
      });
    });
    upstream.on('error', e => { res.statusCode = 502; res.end(`XSportsX bootstrap error: ${e.message}`); });
    req.pipe(upstream);
  } catch (e) { res.statusCode = 400; res.end(`XSportsX bootstrap request error: ${e.message}`); }
});

proxy.listen(publicPort, '0.0.0.0', () => console.log(`XSportsX bootstrap ${BUILD_VERSION} listening on ${publicPort}; app on ${internalPort}`));