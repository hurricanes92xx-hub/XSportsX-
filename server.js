const express = require('express');
const axios = require('axios');
const sharp = require('sharp');

const app = express();
app.disable('x-powered-by');

const PORT = Number(process.env.PORT || 10000);
const BASE = (process.env.PUBLIC_BASE_URL || '').replace(/\/$/, '');
const XTREAM_BASE_URL = (process.env.XTREAM_BASE_URL || '').replace(/\/$/, '');
const XTREAM_USERNAME = process.env.XTREAM_USERNAME || '';
const XTREAM_PASSWORD = process.env.XTREAM_PASSWORD || '';
const TIMEOUT = Number(process.env.REQUEST_TIMEOUT_MS || 9000);
const SCORE_TTL = Number(process.env.SCOREBOARD_TTL_SECONDS || 60) * 1000;
const SOURCE_TTL = Number(process.env.CACHE_TTL_SECONDS || 300) * 1000;

const scoreCache = new Map();
const sourceCache = new Map();
const epgCache = new Map();
const artworkCache = new Map();
const inflight = new Map();

const LEAGUES = {
  nfl: ['NFL', 'football', 'nfl', '🏈'],
  ncaaf: ['NCAA Football', 'football', 'college-football', '🏈'],
  nba: ['NBA', 'basketball', 'nba', '🏀'],
  wnba: ['WNBA', 'basketball', 'wnba', '🏀'],
  ncaab: ['NCAA Basketball', 'basketball', 'mens-college-basketball', '🏀'],
  mlb: ['MLB', 'baseball', 'mlb', '⚾'],
  nhl: ['NHL', 'hockey', 'nhl', '🏒'],
  mls: ['MLS', 'soccer', 'usa.1', '⚽'],
  epl: ['Premier League', 'soccer', 'eng.1', '⚽'],
  ucl: ['UEFA Champions League', 'soccer', 'uefa.champions', '⚽'],
  laliga: ['LaLiga', 'soccer', 'esp.1', '⚽'],
  seriea: ['Serie A', 'soccer', 'ita.1', '⚽'],
  bundesliga: ['Bundesliga', 'soccer', 'ger.1', '⚽'],
  ligue1: ['Ligue 1', 'soccer', 'fra.1', '⚽'],
  ufc: ['UFC', 'mma', 'ufc', '🥊'],
  boxing: ['Boxing', 'boxing', 'boxing', '🥊']
};

const SPORT_RE = /\b(sport|sports|espn|espn\+|fox sports|fs1|fs2|tnt|nba|mlb|nhl|nfl|ncaaf|ncaab|wnba|sec network|acc network|big ten|bally|msg|regional sports|baseball|basketball|football|hockey|soccer|tennis|golf|cbs sports|nbc sports|bein|sky sport|f1|formula|racing|ufc|boxing|fight)\b/i;
const STOP = new Set(['the','and','at','vs','v','fc','cf','sc','club','team','live','tv','hd','fhd','uhd','4k','usa','us','network','sports','sport','channel','east','west','main','backup','feed','event','official']);

const clean = v => String(v ?? '').replace(/\s+/g, ' ').trim();
function norm(v) {
  return clean(v).normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/&/g, ' and ').replace(/[^a-z0-9]+/g, ' ').split(/\s+/).filter(x => x && !STOP.has(x)).join(' ');
}
function tokens(v) { return norm(v).split(' ').filter(Boolean); }
function similarity(a, b) {
  const aa = new Set(tokens(a)), bb = new Set(tokens(b));
  if (!aa.size || !bb.size) return 0;
  let common = 0;
  for (const t of aa) if (bb.has(t)) common++;
  return Math.round((common / Math.min(aa.size, bb.size) * 0.7 + common / new Set([...aa, ...bb]).size * 0.3) * 100);
}
function cached(map, key, ttl, loader) {
  const hit = map.get(key);
  if (hit && hit.expires > Date.now()) return Promise.resolve(hit.value);
  const activeKey = `${map === scoreCache ? 'score' : 'source'}:${key}`;
  if (inflight.has(activeKey)) return inflight.get(activeKey);
  const p = Promise.resolve().then(loader).then(value => {
    map.set(key, { value, expires: Date.now() + ttl });
    return value;
  }).finally(() => inflight.delete(activeKey));
  inflight.set(activeKey, p);
  return p;
}

function baseUrl(req) {
  if (BASE) return BASE;
  const proto = String(req.headers['x-forwarded-proto'] || 'https').split(',')[0];
  return `${proto}://${req.headers.host || 'localhost'}`;
}
function xtreamUrl(action, extra = {}) {
  const u = new URL(`${XTREAM_BASE_URL}/player_api.php`);
  u.searchParams.set('username', XTREAM_USERNAME);
  u.searchParams.set('password', XTREAM_PASSWORD);
  if (action) u.searchParams.set('action', action);
  for (const [k, v] of Object.entries(extra)) u.searchParams.set(k, String(v));
  return u.toString();
}
async function xtream(action, extra = {}) {
  if (!XTREAM_BASE_URL || !XTREAM_USERNAME || !XTREAM_PASSWORD) throw new Error('Xtream source is not configured');
  return (await axios.get(xtreamUrl(action, extra), { timeout: TIMEOUT })).data;
}

function scoreboardUrl(league, date) {
  const l = LEAGUES[league];
  return `https://site.api.espn.com/apis/site/v2/sports/${l[1]}/${l[2]}/scoreboard?dates=${date}&limit=100`;
}

async function leagueEvents(league) {
  if (!LEAGUES[league]) return [];
  return cached(scoreCache, league, SCORE_TTL, async () => {
    const events = [];
    const now = new Date();
    for (let offset = -1; offset <= 2; offset++) {
      const d = new Date(now);
      d.setUTCDate(d.getUTCDate() + offset);
      const date = d.toISOString().slice(0, 10).replace(/-/g, '');
      try {
        const data = (await axios.get(scoreboardUrl(league, date), { timeout: TIMEOUT })).data;
        for (const raw of data?.events || []) {
          const comp = raw.competitions?.[0];
          const competitors = comp?.competitors || [];
          const home = competitors.find(x => x.homeAway === 'home')?.team || competitors[0]?.team || {};
          const away = competitors.find(x => x.homeAway === 'away')?.team || competitors[1]?.team || {};
          if (!home.displayName && !away.displayName) continue;
          events.push({
            id: String(raw.id),
            league,
            start: raw.date || '',
            state: comp?.status?.type?.state || raw.status?.type?.state || 'pre',
            status: comp?.status?.type?.shortDetail || raw.status?.type?.shortDetail || 'Scheduled',
            home: { name: home.displayName || home.shortDisplayName || 'Home', short: home.abbreviation || '', logo: home.logo || home.logos?.[0]?.href || '' },
            away: { name: away.displayName || away.shortDisplayName || 'Away', short: away.abbreviation || '', logo: away.logo || away.logos?.[0]?.href || '' },
            broadcast: (comp?.broadcasts || []).flatMap(x => x.names || [])
          });
        }
      } catch (err) {
        console.error(`[scoreboard] ${league} ${date}: ${err.message}`);
      }
    }
    const unique = new Map(events.map(e => [e.id, e]));
    return [...unique.values()].sort((a, b) => Date.parse(a.start || 0) - Date.parse(b.start || 0));
  });
}

async function allEvents() {
  return (await Promise.all(Object.keys(LEAGUES).map(leagueEvents))).flat();
}

async function xtreamIndex() {
  return cached(sourceCache, 'index', SOURCE_TTL, async () => {
    const [cats, streams] = await Promise.all([xtream('get_live_categories'), xtream('get_live_streams')]);
    const categoryMap = new Map((Array.isArray(cats) ? cats : []).map(c => [String(c.category_id), c.category_name || 'Live TV']));
    const rows = (Array.isArray(streams) ? streams : []).map(s => {
      const extension = String(s.container_extension || 'ts').replace(/[^a-z0-9]/gi, '') || 'ts';
      return {
        id: String(s.stream_id),
        streamId: String(s.stream_id),
        name: s.name || `Channel ${s.stream_id}`,
        category: categoryMap.get(String(s.category_id)) || 'Live TV',
        logo: s.stream_icon || s.thumbnail || '',
        epgId: s.epg_channel_id || '',
        url: `${XTREAM_BASE_URL}/live/${encodeURIComponent(XTREAM_USERNAME)}/${encodeURIComponent(XTREAM_PASSWORD)}/${encodeURIComponent(s.stream_id)}.${extension}`
      };
    });
    return { all: rows, sports: rows.filter(x => SPORT_RE.test(`${x.name} ${x.category}`)) };
  });
}

function decodeEpg(v) {
  const raw = clean(v);
  const compact = raw.replace(/\s+/g, '');
  if (!/^[A-Za-z0-9+/]+={0,2}$/.test(compact) || compact.length < 8 || compact.length % 4 === 1) return raw;
  try {
    const decoded = Buffer.from(compact, 'base64').toString('utf8').replace(/[\u0000-\u001f]/g, ' ').trim();
    return decoded && /[A-Za-z]{2,}/.test(decoded) ? decoded : raw;
  } catch { return raw; }
}

async function shortEpg(streamId) {
  const hit = epgCache.get(streamId);
  if (hit && hit.expires > Date.now()) return hit.value;
  try {
    const data = await xtream('get_short_epg', { stream_id: streamId, limit: 12 });
    const rows = Array.isArray(data?.epg_listings) ? data.epg_listings : [];
    epgCache.set(streamId, { value: rows, expires: Date.now() + 60000 });
    return rows;
  } catch { return hit?.value || []; }
}

function streamScore(stream, event) {
  const text = `${stream.name} ${stream.category}`;
  const away = similarity(text, event.away.name);
  const home = similarity(text, event.home.name);
  const pair = similarity(text, `${event.away.name} ${event.home.name}`);
  const league = similarity(text, LEAGUES[event.league]?.[0] || '');
  let score = pair * 0.48 + away * 0.24 + home * 0.23 + league * 0.05;
  for (const b of event.broadcast || []) if (norm(text).includes(norm(b))) score = Math.max(score, 93);
  if (/\b(4k|uhd)\b/i.test(stream.name)) score += 3;
  if (/\b(fhd|1080)\b/i.test(stream.name)) score += 2;
  if (/\b(backup|alt|test)\b/i.test(stream.name)) score -= 7;
  return Math.round(score);
}

function epgScore(rows, event) {
  let best = { score: 0, item: null };
  const away = tokens(event.away.name), home = tokens(event.home.name);
  for (const item of Array.isArray(rows) ? rows : []) {
    const text = norm(`${decodeEpg(item.title || '')} ${decodeEpg(item.description || '')}`);
    let a = 0, h = 0;
    for (const t of away) if (text.includes(t)) a++;
    for (const t of home) if (text.includes(t)) h++;
    let score = a && h ? 90 : (a || h ? 58 : similarity(text, `${event.away.name} ${event.home.name}`) * 0.7);
    if (item.now_playing === 1 || item.now_playing === '1') score += 8;
    const epgTime = Number(item.start_timestamp || 0) * 1000;
    const gameTime = Date.parse(event.start || '');
    if (epgTime && gameTime) {
      const delta = Math.abs(epgTime - gameTime);
      if (delta < 2 * 3600000) score += 10;
      else if (delta < 6 * 3600000) score += 5;
    }
    if (score > best.score) best = { score: Math.min(100, Math.round(score)), item };
  }
  return best;
}

async function matchStreams(event) {
  const index = await xtreamIndex();
  const direct = index.sports.map(s => ({ ...s, score: streamScore(s, event) })).filter(s => s.score >= 48).sort((a, b) => b.score - a.score);
  if (direct.length >= 2) return direct.slice(0, 12);

  const pool = (index.sports.length ? index.sports : index.all).slice(0, 240);
  const found = [];
  let cursor = 0;
  const worker = async () => {
    while (cursor < pool.length) {
      const stream = pool[cursor++];
      const hit = epgScore(await shortEpg(stream.streamId), event);
      if (hit.score >= 55) found.push({ ...stream, score: hit.score, epgTitle: decodeEpg(hit.item?.title || '') });
    }
  };
  await Promise.all(Array.from({ length: Math.min(12, pool.length) }, worker));
  return [...direct, ...found].sort((a, b) => b.score - a.score).slice(0, 12);
}

async function logoBuffer(url) {
  if (!url) return null;
  const hit = artworkCache.get(`logo:${url}`);
  if (hit && hit.expires > Date.now()) return hit.value;
  try {
    const response = await axios.get(url, {
      timeout: 4500,
      responseType: 'arraybuffer',
      maxContentLength: 1000000,
      headers: { 'User-Agent': 'Mozilla/5.0 (XSportsX)' }
    });
    const buffer = await sharp(Buffer.from(response.data), { failOn: 'none' })
      .resize({ width: 180, height: 180, fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } })
      .png().toBuffer();
    artworkCache.set(`logo:${url}`, { value: buffer, expires: Date.now() + 86400000 });
    return buffer;
  } catch { return null; }
}

async function logoData(url) {
  const buffer = await logoBuffer(url);
  return buffer ? `data:image/png;base64,${buffer.toString('base64')}` : '';
}

function esc(v) {
  return String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function eventSvg(event, awayLogo, homeLogo) {
  const bg = event.state === 'in' ? '#081b14' : '#09111e';
  const accent = event.league === 'ufc' || event.league === 'boxing' ? '#e21d3f' : '#4aa3ff';
  const time = event.start ? new Date(event.start).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '';
  const image = (href, x) => href ? `<image href="${href}" x="${x}" y="150" width="190" height="190" preserveAspectRatio="xMidYMid meet"/>` : `<circle cx="${x + 95}" cy="245" r="76" fill="#172235" stroke="#40516b" stroke-width="3"/>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="560" viewBox="0 0 1000 560"><defs><linearGradient id="g" x1="0" x2="1"><stop stop-color="${bg}"/><stop offset="1" stop-color="#151b28"/></linearGradient></defs><rect width="1000" height="560" rx="34" fill="url(#g)"/><rect x="0" y="0" width="1000" height="8" fill="${accent}"/><text x="40" y="55" fill="#b9c4d4" font-family="Arial,sans-serif" font-size="22" font-weight="700">XSPORTSX • ${esc(LEAGUES[event.league]?.[0] || 'SPORTS')}</text><text x="500" y="112" text-anchor="middle" fill="#ffffff" font-family="Arial,sans-serif" font-size="20" font-weight="700">${esc(event.status)}</text>${image(awayLogo,90)}${image(homeLogo,720)}<text x="500" y="220" text-anchor="middle" fill="#9eabbc" font-family="Arial,sans-serif" font-size="18" font-weight="700">VS</text><text x="500" y="285" text-anchor="middle" fill="#ffffff" font-family="Arial,sans-serif" font-size="28" font-weight="800">${esc(event.away.name)}</text><text x="500" y="325" text-anchor="middle" fill="#ffffff" font-family="Arial,sans-serif" font-size="28" font-weight="800">${esc(event.home.name)}</text><text x="500" y="375" text-anchor="middle" fill="#8d9aac" font-family="Arial,sans-serif" font-size="18">${esc(time)}</text><rect x="42" y="445" width="916" height="1" fill="#334156"/><text x="500" y="492" text-anchor="middle" fill="#6f7f94" font-family="Arial,sans-serif" font-size="16">LIVE SPORTS • STREAM OPTIONS AVAILABLE</text></svg>`;
}

function genericLeagueArtwork(league) {
  const name = LEAGUES[league]?.[0] || 'Sports';
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="560"><rect width="1000" height="560" fill="#0b1018"/><text x="50" y="70" fill="#b8c5d8" font-family="Arial" font-size="24" font-weight="700">XSPORTSX</text><text x="500" y="290" text-anchor="middle" fill="#fff" font-family="Arial" font-size="54" font-weight="800">${esc(name)}</text><text x="500" y="340" text-anchor="middle" fill="#6f7f94" font-family="Arial" font-size="20">LIVE SPORTS</text></svg>`;
}

function eventMeta(req, event) {
  const id = `sport:${event.league}:${event.id}`;
  const artwork = `${baseUrl(req)}/artwork/event/${encodeURIComponent(event.league)}/${encodeURIComponent(event.id)}.png`;
  return {
    id,
    type: 'tv',
    name: `${event.away.name} vs ${event.home.name}`,
    poster: artwork,
    background: artwork,
    description: `${LEAGUES[event.league]?.[0] || 'Sports'} • ${event.status}`,
    releaseInfo: event.start,
    genres: ['Sports', LEAGUES[event.league]?.[0] || 'Sports'],
    sportSource: event.league,
    eventId: event.id,
    event
  };
}

const catalogs = [
  { type: 'tv', id: 'live-now', name: '🔴 Live Now' },
  { type: 'tv', id: 'sports-command-center', name: '🏆 XSportsX Sports' },
  ...Object.entries(LEAGUES).map(([id, l]) => ({ type: 'tv', id, name: `${l[3]} ${l[0]}`, extra: [{ name: 'search', isRequired: false }] }))
];

const manifest = {
  id: 'com.usportz.nuvio',
  version: '3.0.0',
  name: 'XSportsX',
  description: 'XSportsX sports catalogs using live scoreboard data, cached Xtream EPG matching, and real team logos.',
  resources: [
    { name: 'catalog', types: ['tv'] },
    { name: 'meta', types: ['tv'], idPrefixes: ['sport:', 'league:'] },
    { name: 'stream', types: ['tv'], idPrefixes: ['sport:'] }
  ],
  types: ['tv'],
  catalogs,
  behaviorHints: { configurable: false, configurationRequired: false }
};

app.get('/', (req, res) => res.json({ name: 'XSportsX', status: 'ok', manifest: '/manifest.json', health: '/health', version: manifest.version }));
app.get('/health', (req, res) => res.json({ ok: true, version: manifest.version, nuvioCompatible: true, xtreamConfigured: Boolean(XTREAM_BASE_URL && XTREAM_USERNAME && XTREAM_PASSWORD), scoreboards: scoreCache.size, sourceCache: sourceCache.size, uptime: process.uptime() }));
app.get('/manifest.json', (req, res) => res.json(manifest));

app.get('/artwork/:league.svg', (req, res) => {
  const league = String(req.params.league || '').toLowerCase();
  res.type('image/svg+xml').set('Cache-Control', 'public,max-age=86400').send(genericLeagueArtwork(LEAGUES[league] ? league : 'nfl'));
});

async function resolveEvent(league, id) {
  const events = await leagueEvents(league);
  return events.find(e => e.id === String(id)) || null;
}

app.get('/artwork/event/:league/:id.svg', async (req, res) => {
  try {
    const event = await resolveEvent(String(req.params.league).toLowerCase(), req.params.id);
    if (!event) return res.status(404).type('text/plain').send('Event artwork not found');
    const [away, home] = await Promise.all([logoData(event.away.logo), logoData(event.home.logo)]);
    res.type('image/svg+xml').set('Cache-Control', 'public,max-age=60').send(eventSvg(event, away, home));
  } catch (err) {
    console.error('[artwork svg]', err.message);
    res.status(500).type('text/plain').send('Artwork error');
  }
});

app.get('/artwork/event/:league/:id.png', async (req, res) => {
  try {
    const event = await resolveEvent(String(req.params.league).toLowerCase(), req.params.id);
    if (!event) return res.status(404).type('text/plain').send('Event artwork not found');
    const [away, home] = await Promise.all([logoBuffer(event.away.logo), logoBuffer(event.home.logo)]);
    const layers = [];
    if (away) layers.push({ input: away, left: 92, top: 150 });
    if (home) layers.push({ input: home, left: 718, top: 150 });
    const png = await sharp(Buffer.from(eventSvg(event, '', '')), { density: 144, failOn: 'none' }).composite(layers).png().toBuffer();
    res.type('image/png').set('Cache-Control', 'public,max-age=60').send(png);
  } catch (err) {
    console.error('[artwork png]', err.message);
    res.status(500).type('text/plain').send('Artwork error');
  }
});

app.get('/catalog/:type/:id.json', async (req, res) => {
  const id = String(req.params.id || '');
  try {
    let metas = [];
    if (id === 'live-now' || id === 'sports-command-center') {
      const events = await allEvents();
      const now = Date.now();
      metas = events.filter(e => id === 'live-now' ? e.state === 'in' : true).map(e => eventMeta(req, e));
      if (id === 'live-now' && !metas.length) metas = events.filter(e => Date.parse(e.start || 0) >= now - 3600000).slice(0, 50).map(e => eventMeta(req, e));
    } else if (LEAGUES[id]) {
      metas = (await leagueEvents(id)).map(e => eventMeta(req, e));
    }
    res.json({ metas: metas.slice(0, 100) });
  } catch (err) {
    console.error('[catalog]', err.message);
    res.json({ metas: [] });
  }
});

app.get('/meta/:type/:id.json', async (req, res) => {
  const id = String(req.params.id || '');
  try {
    if (!id.startsWith('sport:')) return res.json({ meta: null });
    const [, league, eventId] = id.split(':');
    const event = await resolveEvent(league, eventId);
    res.json({ meta: event ? eventMeta(req, event) : null });
  } catch (err) {
    console.error('[meta]', err.message);
    res.json({ meta: null });
  }
});

app.get('/stream/:type/:id.json', async (req, res) => {
  const id = String(req.params.id || '');
  try {
    if (!id.startsWith('sport:')) return res.json({ streams: [] });
    const [, league, eventId] = id.split(':');
    const event = await resolveEvent(league, eventId);
    if (!event) return res.json({ streams: [] });
    const matches = await matchStreams(event);
    res.json({ streams: matches.map((s, i) => ({ name: `${s.name}${s.epgTitle ? ` • ${s.epgTitle}` : ''}`, title: `${s.score >= 80 ? 'Best match' : 'Matched'} • ${s.category}`, url: s.url, behaviorHints: { bingeGroup: `xsportsx-${league}-${i}` } })) });
  } catch (err) {
    console.error('[stream]', err.message);
    res.json({ streams: [] });
  }
});

app.listen(PORT, () => console.log(`XSportsX ${manifest.version} listening on ${PORT}`));
