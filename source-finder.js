import { URL } from 'node:url';

const MIN_SOURCES = Number(process.env.MIN_SPORTS_SOURCES || 5);
const FETCH_TIMEOUT_MS = Number(process.env.SOURCE_FETCH_TIMEOUT_MS || 7000);
const HEALTH_TIMEOUT_MS = Number(process.env.SOURCE_HEALTH_TIMEOUT_MS || 5000);

// Web discovery is broad, but credential/paid-service endpoints are never accepted.
// This lets the finder discover public M3U/M3U8 streams without harvesting Xtream logins.
const URL_RE = /https?:\/\/[^\s"'<>]+/gi;
const MEDIA_RE = /\.(?:m3u8?|ts)(?:$|[?#])/i;
const CREDENTIAL_RE = /(?:player_api\.php|get\.php|panel_api\.php|xmltv\.php).*?(?:username|password)=/i;

function usablePublicUrl(raw) {
  try {
    const cleaned = raw.replace(/[),.;]+$/, '').replace(/&amp;/g, '&');
    const u = new URL(cleaned);
    if (!['http:', 'https:'].includes(u.protocol)) return null;
    if (CREDENTIAL_RE.test(u.toString())) return null;
    if (/\/login(?:\/|$)|\/signin(?:\/|$)|\/account(?:\/|$)/i.test(u.pathname)) return null;
    return u.toString();
  } catch { return null; }
}

function decodeBase64(value) {
  const s = String(value || '').trim().replace(/\s+/g, '');
  if (!s || !/^[A-Za-z0-9+/_=-]+$/.test(s)) return '';
  try {
    const normalized = s.replace(/-/g, '+').replace(/_/g, '/');
    return Buffer.from(normalized, 'base64').toString('utf8');
  } catch { return ''; }
}

function extractUrls(text) {
  const out = new Set();
  const raw = String(text || '');
  for (const m of raw.matchAll(URL_RE)) {
    const u = usablePublicUrl(m[0]);
    if (u) out.add(u);
  }
  for (const token of raw.split(/\s+/)) {
    if (token.length < 20 || token.length > 8192) continue;
    const decoded = decodeBase64(token);
    for (const m of decoded.matchAll(URL_RE)) {
      const u = usablePublicUrl(m[0]);
      if (u) out.add(u);
    }
  }
  return [...out];
}

async function fetchText(url, timeout = FETCH_TIMEOUT_MS) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeout);
  try {
    const r = await fetch(url, { signal: ctl.signal, redirect: 'follow', headers: { 'user-agent': 'XSportsX-source-finder/2.0' } });
    if (!r.ok) return '';
    return await r.text();
  } catch { return ''; }
  finally { clearTimeout(timer); }
}

async function webSearch(query) {
  const q = encodeURIComponent(`${query} sports (m3u8 OR m3u) live stream`);
  const html = await fetchText(`https://html.duckduckgo.com/html/?q=${q}`);
  return extractUrls(html).filter(u => MEDIA_RE.test(u) || /playlist|stream|iptv/i.test(u));
}

async function iptvOrgSports() {
  const urls = [
    'https://iptv-org.github.io/iptv/categories/sports.m3u',
    'https://iptv-org.github.io/api/streams.json'
  ];
  const texts = await Promise.all(urls.map(fetchText));
  return texts.flatMap(t => extractUrls(t));
}

async function healthCheck(url) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), HEALTH_TIMEOUT_MS);
  const started = Date.now();
  try {
    const r = await fetch(url, {
      method: 'GET', signal: ctl.signal, redirect: 'follow',
      headers: { 'user-agent': 'XSportsX-health/2.0', range: 'bytes=0-4095' }
    });
    const type = (r.headers.get('content-type') || '').toLowerCase();
    const finalUrl = r.url || url;
    const ok = r.ok && (MEDIA_RE.test(finalUrl) || /mpegurl|m3u|video|octet-stream|application\/x-mpegurl/i.test(type));
    return { url, ok, latencyMs: Date.now() - started, status: r.status, contentType: type, finalUrl };
  } catch (error) {
    return { url, ok: false, latencyMs: Date.now() - started, error: error?.name || 'fetch_failed' };
  } finally { clearTimeout(timer); }
}

export async function findPublicSportsSources(event = {}) {
  const terms = [event.home, event.away, event.name, event.league, event.sport].filter(Boolean).join(' ');
  const queries = [terms || 'live sports', `${terms} sports channel`, `${terms} m3u8`, `${terms} m3u`];
  const discovered = new Set(await iptvOrgSports());
  for (const q of queries) for (const u of await webSearch(q)) discovered.add(u);

  const candidates = [...discovered].slice(0, 400);
  const checks = await Promise.all(candidates.map(healthCheck));
  return checks.filter(x => x.ok).sort((a, b) => a.latencyMs - b.latencyMs).slice(0, Math.max(MIN_SOURCES, 48));
}

export async function replenishSources(existing = [], event = {}) {
  const healthy = existing.filter(x => x?.url);
  if (healthy.length >= MIN_SOURCES) return healthy;
  const found = await findPublicSportsSources(event);
  const seen = new Set(healthy.map(x => x.url));
  for (const item of found) {
    if (!seen.has(item.url)) {
      healthy.push({ ...item, source: 'public-web-discovery' });
      seen.add(item.url);
    }
    if (healthy.length >= MIN_SOURCES) break;
  }
  return healthy;
}

export { MIN_SOURCES };
