const http = require('http');
const { URL } = require('url');

const publicPort = Number(process.env.PORT || 10000);
const internalPort = publicPort + 1;
process.env.PORT = String(internalPort);
require('./server.js');

const RESOURCES = new Set(['manifest.json', 'catalog', 'meta', 'stream']);

function rewrite(raw) {
  const u = new URL(raw || '/', 'http://local');
  const parts = u.pathname.split('/').filter(Boolean);
  const resourceIndex = parts.findIndex((p) => RESOURCES.has(p) || p.startsWith('catalog') || p.startsWith('meta') || p.startsWith('stream'));

  if (resourceIndex < 0) return u.pathname + u.search;

  const before = parts.slice(0, resourceIndex).filter((p) => p !== 'v527');
  if (before.length) {
    const token = before[before.length - 1];
    const resource = '/' + parts.slice(resourceIndex).join('/');
    u.pathname = resource;
    u.searchParams.set('config', token);
  } else if (parts[0] === 'v527') {
    u.pathname = '/' + parts.slice(1).join('/');
  }

  return u.pathname + (u.search || '');
}

const proxy = http.createServer((req, res) => {
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
});

proxy.listen(publicPort, '0.0.0.0', () => {
  console.log(`XSportsX bootstrap listening on ${publicPort}; app on ${internalPort}`);
});
