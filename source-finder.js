import { URL } from 'node:url';

const MIN_SOURCES = Number(process.env.MIN_SPORTS_SOURCES || 5);
const FETCH_TIMEOUT_MS = Number(process.env.SOURCE_FETCH_TIMEOUT_MS || 7000);
const HEALTH_TIMEOUT_MS = Number(process.env.SOURCE_HEALTH_TIMEOUT_MS || 5000);

// Only accept feeds from domains you explicitly permit. This prevents the web-search
// fallback from turning into a collector for arbitrary credential/stream sites.
const DEFAULT_ALLOWED = [
  'iptv-org.github.io',
  'raw.githubusercontent.com',
  'github.com'
];
const ALLOWED_HOSTS = new Set(
  (process.env.SOURCE_FINDER_ALLOWED_HOSTS || DEFAULT_ALLOWED.join(','))
    .split(',').map(s => s.trim().toLowerCase()).filter(Boolean)
);

const SPORTS_RE = /\b(sport|sports|live|espn|nfl|nba|nhl|mlb|nascar|f1|formula\s*1|soccer|football|basketball|baseball|hockey|tennis|golf|boxing|mma|ufc|wwe|cricket|rugby)\b/i;
const URL_RE = /https?:\/\/[^\s"'<>]+/gi;

function allowedUrl(raw) {
  try {
    const u = new URL(raw.replace(/[),.;]+$/, ''));
    if (!['http:', 'https:'].includes(u.protocol)) return null;
    const host = u.hostname.toLowerCase();
    const ok = [...ALLOWED_HOSTS].some(h => host === h || host.endsWith(`.${h}`));
    return ok ? u.toString() : null;
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
  for (const m of String(text || '').matchAll(URL_RE)) {
    const u = allowedUrl(m[0]);
    if (u) out.add(u);
  }
  // Also decode Base64-looking tokens found in public feed/search text.
  for (const token of String(text || '').split(/\s+/)) {
    if (token.length < 20 || token.length > 8192) continue;
    const decoded = decodeBase64(token);
    for (const m of decoded.matchAll(URL_RE)) {
      const u = allowedUrl(m[0]);
      if (u) out.add(u);
    }
  }
  return [...out];
}

async function fetchText(url, timeout = FETCH_TIMEOUT_MS) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeout);
  try {
    const r = await fetch(url, { signal: ctl.signal, redirect: 'follow', headers: { 'user-agent': 'XSportsX-source-finder/1.0' } });
    if (!r.ok) return '';
    return await r.text();
  } catch { return ''; }
  finally { clearTimeout(timer); }
}

async function webSearch(query) {
  // DuckDuckGo is used only as discovery. Results are subsequently filtered through
  // ALLOWED_HOSTS before anything can enter the source pool.
  const q = encodeURIComponent(`${query} IPTV sports m3u m3u8`);
  const html = await fetchText(`https://html.duckduckgo.com/html/?q=${q}`);
  return extractUrls(html);
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
      headers: { 'user-agent': 'XSportsX-health/1.0', 'range': 'bytes=0-4095' }
    });
    const type = (r.headers.get('content-type') || '').toLowerCase();
    const ok = r.ok && (/mpegurl|m3u|video|octet-stream|application\/x-mpegurl/.test(type) || /\.m3u8(?:$|\?)/i.test(new URL(url).pathname));
    return { url, ok, latencyMs: Date.now() - started, status: r.status, contentType: type };
  } catch (error) {
    return { url, ok: false, latencyMs: Date.now() - started, error: error?.name || 'fetch_failed' };
  } finally { clearTimeout(timer); }
}

export async function findPublicSportsSources(event = {}) {
  const terms = [event.home, event.away, event.name, event.league, event.sport].filter(Boolean).join(' ');
  const queries = [
    terms || 'live sports',
    `${terms} sports channel`,
    `${terms} m3u8`
  ];
  const discovered = new Set(await iptvOrgSports());
  for (const q of queries) for (const u of await webSearch(q)) discovered.add(u);

  const candidates = [...discovered].slice(0, 250);
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
