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
    return JSON.parse(Buffer.concat([
      d.update(Buffer.from(bodyS, 'base64url')),
      d.final()
    ]).toString('utf8'));
  } catch {
    return null;
  }
}

function tokenFrom(raw) {
  const u = new URL(raw || '/', 'http://local');
  const parts = u.pathname.split('/').filter(Boolean);
  if (!parts.length) return '';
  if (parts[0] === 'v527') return parts[1] || '';
  const resourceIndex = parts.findIndex(p =>
    RESOURCES.has(p) || p.startsWith('catalog') || p.startsWith('meta') || p.startsWith('stream')
  );
  if (resourceIndex > 0) return parts[resourceIndex - 1];
  if (parts.length === 1 && !PUBLIC.has(parts[0]) && !parts[0].endsWith('.json')) return parts[0];
  return '';
}

function rewrite(raw) {
  const u = new URL(raw || '/', 'http://local');
  let parts = u.pathname.split('/').filter(Boolean);
  if (!parts.length) return u.pathname + u.search;
  if (parts[0] === 'v527') parts = parts.slice(1);
  if (!parts.length) {
    u.pathname = '/manifest.json';
    return u.pathname + (u.search || '');
  }
  const resourceIndex = parts.findIndex(p =>
    RESOURCES.has(p) || p.startsWith('catalog') || p.startsWith('meta') || p.startsWith('stream')
  );
  if (resourceIndex < 0) {
    if (parts.length === 1 && !PUBLIC.has(parts[0]) && !parts[0].endsWith('.json')) {
      u.pathname = '/manifest.json';
      u.searchParams.set('config', parts[0]);
    }
    return u.pathname + (u.search || '');
  }
  const before = parts.slice(0, resourceIndex);
  if (before.length) {
    const token = before[before.length - 1];
    u.pathname = '/' + parts.slice(resourceIndex).join('/');
    u.searchParams.set('config', token);
  } else {
    u.pathname = '/' + parts.join('/');
  }
  return u.pathname + (u.search || '');
}

function selectedSports(token) {
  const c = decryptConfig(token);
  const sports = Array.isArray(c?.sports) ? c.sports.filter(Boolean) : [];
  return sports.length ? new Set(sports) : null;
}

function filterPayload(body, token, path) {
  const selected = selectedSports(token);
  if (!selected || !body || typeof body !== 'object') return body;

  // The manifest is the source of truth for what Nuvio displays as addon catalogs.
  if (path === '/manifest.json' && Array.isArray(body.catalogs)) {
    body.catalogs = body.catalogs.filter(c =>
      c.id === 'sports-command-center' ||
      c.id === 'live-now' ||
      c.id === 'starting-soon' ||
      c.id === 'iptv-live' ||
      selected.has(c.id)
    );
  }

  // Also enforce the selection inside aggregate catalogs so a selected user's
  // Live Now/Starting Soon/Command Center rows cannot leak other leagues.
  if (Array.isArray(body.metas)) {
    body.metas = body.metas.filter(meta => {
      const id = String(meta?.id || '');
      if (!id.startsWith('sport:')) return true;
      const league = id.split(':')[1];
      return selected.has(league);
    });
  }

  return body;
}

const proxy = http.createServer((req, res) => {
  try {
    const token = tokenFrom(req.url);
    const path = rewrite(req.url);
    const headers = { ...req.headers, host: `127.0.0.1:${internalPort}` };
    const upstream = http.request({
      hostname: '127.0.0.1',
      port: internalPort,
      path,
      method: req.method,
      headers
    }, (response) => {
      const contentType = String(response.headers['content-type'] || '');
      const shouldFilter = Boolean(token) && contentType.includes('application/json') &&
        (path === '/manifest.json' || path.startsWith('/catalog/'));

      if (!shouldFilter) {
        res.writeHead(response.statusCode || 502, response.headers);
        return response.pipe(res);
      }

      const chunks = [];
      response.on('data', chunk => chunks.push(chunk));
      response.on('end', () => {
        try {
          const text = Buffer.concat(chunks).toString('utf8');
          const body = filterPayload(JSON.parse(text), token, path);
          const out = Buffer.from(JSON.stringify(body));
          const outHeaders = { ...response.headers, 'content-length': String(out.length) };
          delete outHeaders['transfer-encoding'];
          res.writeHead(response.statusCode || 502, outHeaders);
          res.end(out);
        } catch (err) {
          res.writeHead(response.statusCode || 502, response.headers);
          res.end(Buffer.concat(chunks));
        }
      });
    });
    upstream.on('error', err => {
      res.statusCode = 502;
      res.end(`XSportsX bootstrap error: ${err.message}`);
    });
    req.pipe(upstream);
  } catch (err) {
    res.statusCode = 400;
    res.end(`XSportsX bootstrap request error: ${err.message}`);
  }
});

proxy.listen(publicPort, '0.0.0.0', () => {
  console.log(`XSportsX bootstrap listening on ${publicPort}; app on ${internalPort}`);
});
