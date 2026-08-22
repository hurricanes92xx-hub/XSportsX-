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

const SPORT_ALIASES = {
  nfl: ['nfl', 'football', 'american football'],
  ncaaf: ['ncaaf', 'ncaafb', 'ncaa football', 'college football', 'college-football'],
  nba: ['nba'],
  wnba: ['wnba'],
  ncaab: ['ncaab', 'ncaamb', 'ncaa basketball', 'college basketball', 'mens-college-basketball'],
  mlb: ['mlb'],
  nhl: ['nhl'],
  mls: ['mls'],
  epl: ['epl', 'premier league', 'english premier league'],
  ucl: ['ucl', 'uefa champions league', 'champions league'],
  laliga: ['laliga', 'la liga'],
  seriea: ['seriea', 'serie a'],
  bundesliga: ['bundesliga'],
  ligue1: ['ligue1', 'ligue 1'],
  ufc: ['ufc', 'mma'],
  boxing: ['boxing', 'box']
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
  for (const [id, aliases] of Object.entries(SPORT_ALIASES)) {
    if (aliases.includes(raw)) return id;
  }
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
      u.pathname = '/manifest.json'; u.searchParams.set('config', parts[0]);
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
    body.version = '7.0.0';
    body.id = `community.xsportsx.${crypto.createHash('sha256').update(String(token)).digest('hex').slice(0, 12)}`;
    if (Array.isArray(body.catalogs) && selected) {
      body.catalogs = body.catalogs.filter(c =>
        c.id === 'sports-command-center' ||
        c.id === 'live-now' ||
        c.id === 'starting-soon' ||
        c.id === 'iptv-live' ||
        isSelected(selected, c.id)
      );
    }
  }

  if (Array.isArray(body.metas) && selected) {
    body.metas = body.metas.filter(meta => {
      const id = String(meta?.id || '');
      if (id.startsWith('sport:')) return isSelected(selected, id.split(':')[1]);
      if (id.startsWith('xtream:')) return true;
      return true;
    });
  }

  return body;
}

const proxy = http.createServer((req, res) => {
  try {
    const token = tokenFrom(req.url);
    const path = rewrite(req.url);
    const upstream = http.request({
      hostname: '127.0.0.1',
      port: internalPort,
      path,
      method: req.method,
      headers: { ...req.headers, host: `127.0.0.1:${internalPort}` }
    }, response => {
      const ct = String(response.headers['content-type'] || '');
      const filter = Boolean(token) && ct.includes('application/json') && (path === '/manifest.json' || path.startsWith('/catalog/'));
      if (!filter) {
        res.writeHead(response.statusCode || 502, response.headers);
        return response.pipe(res);
      }

      const chunks = [];
      response.on('data', c => chunks.push(c));
      response.on('end', () => {
        try {
          const body = filterPayload(JSON.parse(Buffer.concat(chunks).toString('utf8')), token, path);
          const out = Buffer.from(JSON.stringify(body));
          const selected = selectedSports(token);
          const selectedHeader = selected ? [...selected].join(',') : 'configuration-unreadable';
          const h = {
            ...response.headers,
            'content-length': String(out.length),
            'cache-control': 'no-store, no-cache, must-revalidate, proxy-revalidate',
            'x-xsportsx-selected-leagues': selectedHeader,
            'x-xsportsx-configured': selected ? 'true' : 'false'
          };
          delete h['transfer-encoding'];
          res.writeHead(response.statusCode || 502, h);
          res.end(out);
        } catch {
          res.writeHead(response.statusCode || 502, response.headers);
          res.end(Buffer.concat(chunks));
        }
      });
    });
    upstream.on('error', e => { res.statusCode = 502; res.end(`XSportsX bootstrap error: ${e.message}`); });
    req.pipe(upstream);
  } catch (e) {
    res.statusCode = 400;
    res.end(`XSportsX bootstrap request error: ${e.message}`);
  }
});

proxy.listen(publicPort, '0.0.0.0', () => console.log(`XSportsX bootstrap listening on ${publicPort}; app on ${internalPort}`));
