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

function decryptConfig(token) {
  try {
    const [ivS, tagS, bodyS] = String(token || '').split('.');
    if (!ivS || !tagS || !bodyS) return null;
    const d = crypto.createDecipheriv('aes-256-gcm', KEY, Buffer.from(ivS, 'base64url'));
    d.setAuthTag(Buffer.from(tagS, 'base64url'));
    return JSON.parse(Buffer.concat([d.update(Buffer.from(bodyS, 'base64url')), d.final()]).toString('utf8'));
  } catch { return null; }
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
  const sports = Array.isArray(c?.sports) ? c.sports.filter(Boolean) : [];
  return sports.length ? new Set(sports) : null;
}

function connectionId(token) {
  return `community.xsportsx.${crypto.createHash('sha256').update(String(token)).digest('hex').slice(0,16)}`;
}

function filterPayload(body, token, path) {
  const selected = selectedSports(token);
  if (!selected || !body || typeof body !== 'object') return body;

  if (path === '/manifest.json') {
    // A unique addon ID per private connection prevents Nuvio from reusing
    // the old catalog definition belonging to another XSportsX connection.
    body.id = connectionId(token);
    body.version = '6.2.0';
    body.name = 'XSportsX';
    if (Array.isArray(body.catalogs)) {
      body.catalogs = body.catalogs.filter(c =>
        c.id === 'sports-command-center' ||
        c.id === 'live-now' ||
        c.id === 'starting-soon' ||
        c.id === 'iptv-live' ||
        selected.has(c.id)
      );
    }
  }

  // Enforce the same selection in Live Now, Starting Soon and Command Center
  // so an old aggregate response cannot reintroduce unselected leagues.
  if (Array.isArray(body.metas)) {
    body.metas = body.metas.filter(meta => {
      const id = String(meta?.id || '');
      if (!id.startsWith('sport:')) return true;
      return selected.has(id.split(':')[1]);
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
      const shouldFilter = Boolean(token) && ct.includes('application/json') &&
        (path === '/manifest.json' || path.startsWith('/catalog/'));

      if (!shouldFilter) {
        res.writeHead(response.statusCode || 502, response.headers);
        return response.pipe(res);
      }

      const chunks = [];
      response.on('data', c => chunks.push(c));
      response.on('end', () => {
        try {
          const body = filterPayload(
            JSON.parse(Buffer.concat(chunks).toString('utf8')),
            token,
            path
          );
          const out = Buffer.from(JSON.stringify(body));
          const h = {
            ...response.headers,
            'content-length': String(out.length),
            'cache-control': 'no-store, no-cache, must-revalidate, proxy-revalidate',
            'pragma': 'no-cache',
            'expires': '0'
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
    upstream.on('error', e => {
      res.statusCode = 502;
      res.end(`XSportsX bootstrap error: ${e.message}`);
    });
    req.pipe(upstream);
  } catch (e) {
    res.statusCode = 400;
    res.end(`XSportsX bootstrap request error: ${e.message}`);
  }
});

proxy.listen(publicPort, '0.0.0.0', () =>
  console.log(`XSportsX bootstrap listening on ${publicPort}; app on ${internalPort}`)
);
