import dns from 'node:dns/promises';
import net from 'node:net';
import { URL } from 'node:url';

const MAX_FETCH_BYTES = 2 * 1024 * 1024;
const MAX_TEXT_BYTES = 4 * 1024 * 1024;
const MAX_DECODED_BYTES = 2 * 1024 * 1024;
const MAX_LINKS = 100;
const MAX_LAYERS = 3;
const FETCH_TIMEOUT_MS = 9000;
const HEALTH_TIMEOUT_MS = 6000;

const PRIVATE_V4 = [
  [/^10\./, 'private'],
  [/^127\./, 'loopback'],
  [/^169\.254\./, 'link-local'],
  [/^172\.(1[6-9]|2\d|3[0-1])\./, 'private'],
  [/^192\.0\.0\./, 'special'],
  [/^192\.168\./, 'private'],
  [/^198\.18\./, 'benchmark'],
  [/^198\.19\./, 'benchmark'],
  [/^224\./, 'multicast'],
  [/^0\./, 'unspecified']
];

function isPrivateIp(ip) {
  if (net.isIPv4(ip)) return PRIVATE_V4.some(([re]) => re.test(ip));
  if (net.isIPv6(ip)) {
    const x = ip.toLowerCase();
    return x === '::' || x === '::1' || x.startsWith('fc') || x.startsWith('fd') || x.startsWith('fe80:') || x.startsWith('ff');
  }
  return true;
}

async function assertSafeUrl(input, allowHttp = true) {
  const u = new URL(input);
  if ((allowHttp ? !['http:', 'https:'] : u.protocol !== 'https:')) throw new Error('Only HTTP(S) URLs are allowed');
  if (u.username || u.password) throw new Error('URLs containing credentials are not allowed');
  const host = u.hostname.replace(/^\[|\]$/g, '');
  if (!host) throw new Error('Missing hostname');
  const addresses = net.isIP(host) ? [host] : await dns.lookup(host, { all: true }).then(rows => rows.map(r => r.address));
  if (!addresses.length || addresses.some(isPrivateIp)) throw new Error('Private, local, or reserved hosts are blocked');
  return u;
}

function normalizeBase64(s) {
  let x = String(s ?? '').trim();
  if (x.startsWith('data:')) {
    const comma = x.indexOf(',');
    if (comma >= 0) x = x.slice(comma + 1);
  }
  x = x.replace(/\s+/g, '').replace(/-/g, '+').replace(/_/g, '/');
  if (!x || x.length > 8 * 1024 * 1024 || !/^[A-Za-z0-9+/]*={0,2}$/.test(x)) return null;
  const padded = x + '='.repeat((4 - x.length % 4) % 4);
  if (padded.length % 4 !== 0) return null;
  return padded;
}

function decodeBase64(input) {
  const normalized = normalizeBase64(input);
  if (!normalized) throw new Error('Invalid Base64');
  const buf = Buffer.from(normalized, 'base64');
  if (!buf.length) throw new Error('Base64 decoded to empty data');
  if (buf.length > MAX_DECODED_BYTES) throw new Error('Decoded payload is too large');
  return buf.toString('utf8').replace(/^\uFEFF/, '');
}

function looksLikeBase64(value) {
  const x = String(value).replace(/\s+/g, '');
  return x.length >= 16 && x.length <= 8 * 1024 * 1024 && x.length % 4 <= 2 && /^[A-Za-z0-9+/_-]+={0,2}$/.test(x);
}

function extractBase64Candidates(text) {
  const out = new Set();
  const add = value => {
    if (!value) return;
    const clean = String(value).trim();
    if (looksLikeBase64(clean)) out.add(clean);
  };

  // Common explicit wrappers first.
  for (const m of String(text).matchAll(/(?:base64|b64|data:[^;,]+;base64)\s*[:=,]\s*([A-Za-z0-9+/_-]{16,}(?:={0,2}))/gi)) add(m[1]);
  // Standalone long Base64 blobs, bounded to avoid treating normal prose as Base64.
  for (const m of String(text).matchAll(/(?<![A-Za-z0-9+/_-])([A-Za-z0-9+/_-]{40,}={0,2})(?![A-Za-z0-9+/_-])/g)) add(m[1]);
  return [...out].slice(0, 50);
}

function extractUrls(text) {
  const found = new Set();
  const add = raw => {
    try {
      const u = new URL(raw.replace(/["'<>\]\[),;]+$/g, ''));
      if (u.protocol === 'http:' || u.protocol === 'https:') found.add(u.href);
    } catch {}
  };
  for (const m of String(text).matchAll(/https?:\/\/[^\s"'<>]+/gi)) add(m[0]);
  return [...found].slice(0, MAX_LINKS);
}

async function fetchText(url) {
  const safe = await assertSafeUrl(url);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(safe, { redirect: 'manual', signal: controller.signal, headers: { accept: 'text/html,text/plain,application/javascript,application/json,*/*' } });
    if (res.status >= 300 && res.status < 400) {
      const location = res.headers.get('location');
      if (!location) throw new Error(`Redirect ${res.status} without Location`);
      const next = new URL(location, safe).href;
      await assertSafeUrl(next);
      return fetchText(next);
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const len = Number(res.headers.get('content-length') || 0);
    if (len > MAX_FETCH_BYTES) throw new Error('Source page is too large');
    const reader = res.body?.getReader();
    if (!reader) return { url: safe.href, text: await res.text() };
    const chunks = [];
    let total = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > MAX_FETCH_BYTES) { await reader.cancel(); throw new Error('Source page is too large'); }
      chunks.push(Buffer.from(value));
    }
    return { url: safe.href, text: Buffer.concat(chunks).toString('utf8') };
  } finally { clearTimeout(timer); }
}

async function healthCheck(url) {
  const started = Date.now();
  let safe;
  try { safe = await assertSafeUrl(url); } catch (e) { return { url, ok: false, status: null, latencyMs: Date.now() - started, error: e.message }; }
  const doRequest = async method => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS);
    try {
      return await fetch(safe, { method, redirect: 'manual', signal: controller.signal, headers: { 'user-agent': 'XSportsX-LinkHealth/1.0', ...(method === 'GET' ? { range: 'bytes=0-1' } : {}) } });
    } finally { clearTimeout(timer); }
  };
  try {
    let res = await doRequest('HEAD');
    if (res.status === 405 || res.status === 501) res = await doRequest('GET');
    if (res.status >= 300 && res.status < 400) {
      const location = res.headers.get('location');
      if (location) { const next = new URL(location, safe).href; await assertSafeUrl(next); }
    }
    return { url: safe.href, ok: res.ok || (res.status >= 300 && res.status < 400), status: res.status, latencyMs: Date.now() - started, contentType: res.headers.get('content-type') || '' };
  } catch (e) {
    return { url: safe.href, ok: false, status: null, latencyMs: Date.now() - started, error: e.name === 'AbortError' ? 'timeout' : e.message };
  }
}

export async function scanBase64Input({ base64 = '', site = '', health = true } = {}) {
  let source = String(base64 || '');
  let sourceUrl = null;
  if (site) {
    const page = await fetchText(site);
    sourceUrl = page.url;
    source = `${page.text}\n${source}`;
  }
  if (Buffer.byteLength(source, 'utf8') > MAX_TEXT_BYTES) throw new Error('Input is too large');

  const decoded = [];
  const seenPayloads = new Set();
  let queue = extractBase64Candidates(source).map(value => ({ value, layer: 1 }));
  if (base64 && looksLikeBase64(base64)) queue.unshift({ value: base64, layer: 1 });

  while (queue.length && decoded.length < 100) {
    const item = queue.shift();
    const normalized = normalizeBase64(item.value);
    if (!normalized || seenPayloads.has(normalized)) continue;
    seenPayloads.add(normalized);
    try {
      const text = decodeBase64(item.value);
      if (!text || /[\u0000-\u0008\u000B\u000C\u000E-\u001F]/.test(text.slice(0, 200))) continue;
      const urls = extractUrls(text);
      decoded.push({ layer: item.layer, inputLength: normalized.length, text: text.slice(0, 200000), urls });
      if (item.layer < MAX_LAYERS) for (const nested of extractBase64Candidates(text)) queue.push({ value: nested, layer: item.layer + 1 });
    } catch {}
  }

  const links = [...new Set(decoded.flatMap(x => x.urls))].slice(0, MAX_LINKS);
  const healthResults = health ? await Promise.all(links.map(healthCheck)) : [];
  return { ok: true, sourceUrl, decodedCount: decoded.length, linkCount: links.length, decoded, links: healthResults };
}

const html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>XSportsX Base64 Link Tool</title><style>body{font:15px system-ui;background:#0d1117;color:#e6edf3;max-width:1000px;margin:30px auto;padding:0 18px}textarea,input{width:100%;box-sizing:border-box;background:#161b22;color:inherit;border:1px solid #30363d;border-radius:8px;padding:12px;margin:6px 0 14px}button{background:#238636;color:white;border:0;border-radius:8px;padding:11px 16px;font-weight:700;cursor:pointer}.card{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px;margin:12px 0}pre{white-space:pre-wrap;word-break:break-word;max-height:420px;overflow:auto}.ok{color:#3fb950}.bad{color:#f85149}</style></head><body><h1>Base64 Decoder + Link Health</h1><p>Paste Base64 or enter a public HTTP(S) site. The scanner decodes embedded Base64, extracts HTTP(S) links, and checks them without following unsafe/private hosts.</p><label>Site URL</label><input id="site" placeholder="https://example.com/page"><label>Base64 / code (optional)</label><textarea id="base64" rows="9" placeholder="Paste Base64, HTML, JavaScript, JSON, or M3U text here"></textarea><button onclick="scan()">Decode + Health Check</button><div id="out"></div><script>async function scan(){const out=document.getElementById('out');out.innerHTML='<div class=card>Scanning…</div>';try{const r=await fetch('/tools/base64/scan',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({site:document.getElementById('site').value,base64:document.getElementById('base64').value,health:true})});const j=await r.json();if(!r.ok)throw Error(j.error||'Scan failed');let h='<div class=card><b>'+j.decodedCount+'</b> decoded payloads • <b>'+j.linkCount+'</b> links</div>';for(const d of j.decoded)h+='<div class=card><b>Layer '+d.layer+'</b><pre>'+esc(d.text)+'</pre></div>';for(const x of j.links)h+='<div class=card><span class="'+(x.ok?'ok':'bad')+'">'+(x.ok?'✓ HEALTHY':'✕ FAILED')+'</span> '+esc(x.url)+' — '+(x.status??'ERR')+' — '+x.latencyMs+'ms'+(x.error?' — '+esc(x.error):'')+'</div>';out.innerHTML=h||'<div class=card>No Base64 payloads found.</div>'}catch(e){out.innerHTML='<div class="card bad">'+esc(e.message)+'</div>'}}function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}</script></body></html>`;

export async function handleBase64Tool(req, res) {
  const url = new URL(req.url || '/', 'http://localhost');
  if (url.pathname === '/tools/base64' && req.method === 'GET') {
    res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' });
    res.end(html); return true;
  }
  if (url.pathname === '/tools/base64/scan' && req.method === 'POST') {
    try {
      let body = ''; for await (const chunk of req) { body += chunk; if (body.length > MAX_TEXT_BYTES) throw new Error('Request is too large'); }
      const input = JSON.parse(body || '{}');
      const result = await scanBase64Input(input);
      res.writeHead(200, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store', 'access-control-allow-origin': '*' });
      res.end(JSON.stringify(result));
    } catch (e) {
      res.writeHead(400, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
      res.end(JSON.stringify({ ok: false, error: e.message || 'Scan failed' }));
    }
    return true;
  }
  return false;
}
