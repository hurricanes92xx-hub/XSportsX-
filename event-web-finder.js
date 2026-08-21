import { URL } from 'node:url';

const TIMEOUT_MS = Number(process.env.EVENT_WEB_TIMEOUT_MS || 7000);
const MAX_RESULTS = Number(process.env.EVENT_WEB_MAX_RESULTS || 30);

const OFFICIAL_HOSTS = new Set([
  'ufc.com', 'ufcfightpass.com', 'espn.com', 'espnplus.com',
  'paramountplus.com', 'cbssports.com', 'fifa.com', 'redbull.com',
  'pluto.tv', 'tubitv.com', 'therokuchannel.roku.com', 'youtube.com', 'youtu.be'
]);

const MEDIA_RE = /\.(?:m3u8?|mpd)(?:$|[?#])/i;
const URL_RE = /https?:\/\/[^\s"'<>]+/gi;

function cleanUrl(raw) {
  try {
    const u = new URL(raw.replace(/[),.;]+$/, ''));
    if (!['http:', 'https:'].includes(u.protocol)) return null;
    return u.toString();
  } catch { return null; }
}

function officialOrPublic(url) {
  try {
    const u = new URL(url);
    const host = u.hostname.toLowerCase();
    return [...OFFICIAL_HOSTS].some(h => host === h || host.endsWith(`.${h}`));
  } catch { return false; }
}

async function fetchText(url) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), TIMEOUT_MS);
  try {
    const r = await fetch(url, { signal: ctl.signal, redirect: 'follow', headers: { 'user-agent': 'XSportsX-event-finder/1.0' } });
    return r.ok ? await r.text() : '';
  } catch { return ''; }
  finally { clearTimeout(timer); }
}

async function searchWeb(query) {
  const q = encodeURIComponent(query);
  const html = await fetchText(`https://html.duckduckgo.com/html/?q=${q}`);
  return [...html.matchAll(URL_RE)].map(m => cleanUrl(m[0])).filter(Boolean);
}

function queriesForEvent(event = {}) {
  const home = event.home || '';
  const away = event.away || '';
  const name = event.name || '';
  const league = event.league || '';
  const sport = event.sport || '';
  const base = [name, home, away, league, sport].filter(Boolean).join(' ');
  const isUfc = /\b(ufc|mma)\b/i.test(`${base} ${event.type || ''}`);
  return isUfc ? [
    `${base} official watch live`,
    `${base} UFC watch`,
    `${base} live stream official`,
    `site:ufc.com ${base} watch`
  ] : [
    `${base} official watch live`,
    `${base} live stream official`,
    `${base} watch live ${sport}`,
    `${base} live m3u8`
  ];
}

export async function findEventWebStreams(event = {}) {
  const urls = new Set();
  for (const q of queriesForEvent(event)) {
    for (const u of await searchWeb(q)) urls.add(u);
  }

  const results = [];
  for (const url of urls) {
    // Prefer official event/watch pages. Direct media URLs are accepted only
    // when they come from an explicitly trusted public broadcaster/platform.
    if (officialOrPublic(url)) {
      results.push({ url, source: 'event-web-discovery', trusted: true, directMedia: MEDIA_RE.test(url) });
    }
  }

  return results.slice(0, MAX_RESULTS);
}

export function classifyEvent(event = {}) {
  const text = JSON.stringify(event);
  if (/\b(ufc|mma|fight night|fightpass)\b/i.test(text)) return 'ufc';
  if (/\b(nfl|nba|nhl|mlb|nascar|f1|formula 1|soccer|football|basketball|baseball|hockey|tennis|golf|boxing|wwe|cricket|rugby)\b/i.test(text)) return 'sports';
  return 'sports';
}
