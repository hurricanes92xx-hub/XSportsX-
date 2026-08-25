const http = require('http');
const { spawn } = require('child_process');
const crypto = require('crypto');

const publicPort = Number(process.env.PORT || 10000);
const upstreamPort = publicPort + 1;
const TTL = 5 * 60 * 1000;
const sessions = new Map();

const child = spawn(process.execPath, ['bootstrap.js'], {
  env: { ...process.env, PORT: String(upstreamPort) },
  stdio: 'inherit'
});
child.on('exit', code => process.exit(code ?? 1));

function json(res, status, body) {
  const data = Buffer.from(JSON.stringify(body));
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store',
    'content-length': data.length,
    'x-xsportsx-pairing': 'v1'
  });
  res.end(data);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let raw = '';
    req.on('data', d => {
      raw += d;
      if (raw.length > 32768) { req.destroy(); reject(new Error('request too large')); }
    });
    req.on('end', () => {
      try { resolve(JSON.parse(raw || '{}')); } catch { reject(new Error('invalid json')); }
    });
    req.on('error', reject);
  });
}

function validSource(c) {
  if (!c || typeof c !== 'object') return false;
  const type = String(c.type || '').toUpperCase();
  if (type === 'M3U') return String(c.m3uUrl || '').startsWith('http');
  return String(c.server || '').startsWith('http') && String(c.username || '').trim() && String(c.password || '').trim();
}

function cleanup() {
  const now = Date.now();
  for (const [code, s] of sessions) if (s.expiresAt <= now || s.completed) sessions.delete(code);
}
setInterval(cleanup, 30000).unref();

const server = http.createServer(async (req, res) => {
  const path = new URL(req.url || '/', 'http://local').pathname;
  try {
    if (path === '/pair/start' && req.method === 'GET') {
      cleanup();
      let pairCode;
      do { pairCode = String(crypto.randomInt(100000, 1000000)); } while (sessions.has(pairCode));
      const sessionId = crypto.randomBytes(18).toString('base64url');
      sessions.set(pairCode, { sessionId, expiresAt: Date.now() + TTL, approved: false, completed: false, sourceConfig: null, deviceToken: null });
      return json(res, 200, { pairCode, sessionId, qrPayload: `xsportsx://pair/${pairCode}`, expiresIn: 300 });
    }

    if (path === '/pair/approve' && req.method === 'POST') {
      const body = await readBody(req);
      const code = String(body.pairCode || '').trim();
      const session = sessions.get(code);
      if (!session || session.expiresAt <= Date.now() || session.completed) return json(res, 410, { error: 'Pairing code expired or already used' });
      const sourceConfig = body.sourceConfig;
      if (!validSource(sourceConfig)) return json(res, 400, { error: 'No valid source is configured on the phone' });
      session.sourceConfig = sourceConfig;
      session.deviceToken = crypto.randomBytes(24).toString('base64url');
      session.approved = true;
      return json(res, 200, { sessionId: session.sessionId, deviceToken: session.deviceToken });
    }

    if (path === '/pair/status' && req.method === 'GET') {
      const sessionId = String(new URL(req.url || '/', 'http://local').searchParams.get('sessionId') || '');
      const session = [...sessions.values()].find(s => s.sessionId === sessionId);
      if (!session || session.expiresAt <= Date.now() || session.completed) return json(res, 410, { error: 'Pairing session expired or completed' });
      return json(res, 200, { approved: !!session.approved, deviceToken: session.approved ? session.deviceToken : null, sourceConfig: session.approved ? session.sourceConfig : null });
    }

    if (path === '/pair/complete' && req.method === 'POST') {
      const body = await readBody(req);
      const session = [...sessions.values()].find(s => s.sessionId === String(body.sessionId || ''));
      if (!session || session.expiresAt <= Date.now() || session.completed) return json(res, 410, { error: 'Pairing session expired or completed' });
      if (!session.approved || String(body.deviceToken || '') !== session.deviceToken) return json(res, 409, { error: 'Waiting for phone approval' });
      session.completed = true;
      const deviceId = crypto.createHash('sha256').update(session.sessionId).digest('hex').slice(0, 16);
      for (const [code, value] of sessions) if (value === session) sessions.delete(code);
      return json(res, 200, { sessionId: session.sessionId, deviceId, sourceConfig: session.sourceConfig });
    }

    const upstream = http.request({
      hostname: '127.0.0.1', port: upstreamPort, path: req.url, method: req.method,
      headers: { ...req.headers, host: `127.0.0.1:${upstreamPort}` }
    }, r => {
      res.writeHead(r.statusCode || 502, r.headers);
      r.pipe(res);
    });
    upstream.on('error', e => { if (!res.headersSent) res.writeHead(502); res.end(e.message); });
    req.pipe(upstream);
  } catch (e) {
    if (!res.headersSent) json(res, 400, { error: e.message || 'Bad request' });
  }
});

server.listen(publicPort, '0.0.0.0', () => console.log(`XSportsX pairing proxy public ${publicPort} -> ${upstreamPort}`));
