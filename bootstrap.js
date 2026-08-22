const http = require('http');
const { URL } = require('url');

const publicPort = Number(process.env.PORT || 10000);
const internalPort = publicPort + 1;
process.env.PORT = String(internalPort);
require('./server.js');

// Standard Stremio/Nuvio parameterized addon routing:
// /<config>/manifest.json
// /<config>/catalog/tv/<id>.json
// /<config>/meta/tv/<id>.json
// /<config>/stream/tv/<id>.json
const RESOURCES = new Set(['manifest.json', 'catalog', 'meta', 'stream']);
const PUBLIC = new Set(['configure', 'health', 'xtream-health', 'artwork', 'qr']);

function rewrite(raw) {
  const u = new URL(raw || '/', 'http://local');
  let parts = u.pathname.split('/').filter(Boolean);

  if (!parts.length) return u.pathname + u.search;
  // Keep backwards compatibility, but it is no longer required.
  if (parts[0] === 'v527') parts = parts.slice(1);
  if (!parts.length) {
    u.pathname = '/manifest.json';
    return u.pathname + (u.search || '');
  }

  const resourceIndex = parts.findIndex((p) =>
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

const proxy = http.createServer((req, res) => {
  try {
    const path = rewrite(req.url);
    const headers = { ...req.headers, host: `127.0.0.1:${internalPort}` };
    const upstream = http.request({
      hostname: '127.0.0.1',
      port: internalPort,
      path,
      method: req.method,
      headers
    }, (response) => {
      res.writeHead(response.statusCode || 502, response.headers);
      response.pipe(res);
    });
    upstream.on('error', (err) => {
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
