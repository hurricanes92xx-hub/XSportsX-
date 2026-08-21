import crypto from 'node:crypto';

const UA = process.env.REDDIT_USER_AGENT || 'XSportsX/1.0 authorized-source-monitor';
const seen = new Map();

function normalizeSubreddit(input) {
  const s = String(input || '').trim();
  const m = s.match(/(?:reddit\.com|old\.reddit\.com|www\.reddit\.com)\/r\/([A-Za-z0-9_]+)|^r\/([A-Za-z0-9_]+)$|^([A-Za-z0-9_]+)$/i);
  return m ? (m[1] || m[2] || m[3]) : null;
}
function decodeB64(value) {
  const s = String(value || '').replace(/\s+/g, '');
  if (s.length < 24 || s.length % 4 === 1 || !/^[A-Za-z0-9+/=_-]+$/.test(s)) return null;
  try {
    const normalized = s.replace(/-/g, '+').replace(/_/g, '/');
    const out = Buffer.from(normalized, 'base64').toString('utf8');
    if (!out || /�/.test(out)) return null;
    return out;
  } catch { return null; }
}
function extractB64(text) {
  const hits = [];
  const parts = String(text || '').match(/[A-Za-z0-9+/_=-]{32,}/g) || [];
  for (const p of parts) { const d = decodeB64(p); if (d && (d.includes('http://') || d.includes('https://') || d.includes('#EXTM3U') || d.includes('username=') || d.includes('stalker'))) hits.push(d); }
  return hits;
}
function urls(text) { return [...new Set((String(text || '').match(/https?:\/\/[^\s"'<>]+/gi) || []).map(x => x.replace(/[\]\[),;]+$/g, '')))]; }
function classify(text, url) {
  const s = `${text}\n${url}`.toLowerCase();
  if (s.includes('#extm3u') || s.includes('#extinf')) return 'm3u';
  if (s.includes('player_api.php') || s.includes('get.php') || /[?&]username=/.test(s)) return 'xtream';
  if (s.includes('stalker') || s.includes('/portal.php')) return 'stalker';
  return 'direct';
}

export async function scanSubreddit(input, { maxPosts = 100 } = {}) {
  const subreddit = normalizeSubreddit(input);
  if (!subreddit) throw new Error('Enter a valid subreddit URL such as https://www.reddit.com/r/example');
  const endpoint = `https://www.reddit.com/r/${encodeURIComponent(subreddit)}/new.json?limit=${Math.min(Math.max(Number(maxPosts) || 100, 1), 100)}`;
  const r = await fetch(endpoint, { headers: { 'user-agent': UA, accept: 'application/json' } });
  if (!r.ok) throw new Error(`Reddit returned HTTP ${r.status}`);
  const body = await r.json();
  const posts = body?.data?.children || [];
  const discoveries = [];
  for (const child of posts) {
    const p = child?.data;
    if (!p?.id) continue;
    const text = `${p.title || ''}\n${p.selftext || ''}`;
    const decoded = extractB64(text);
    const candidates = [text, ...decoded];
    for (const sourceText of candidates) {
      for (const url of urls(sourceText)) {
        discoveries.push({ id: crypto.createHash('sha256').update(`${p.id}|${url}`).digest('hex').slice(0, 24), postId: p.id, title: p.title || '', subreddit, url, type: classify(sourceText, url), details: `Discovered in Reddit post ${p.id}`, discoveredAt: p.created_utc ? new Date(p.created_utc * 1000).toISOString() : new Date().toISOString() });
      }
    }
  }
  return { subreddit, postsChecked: posts.length, discoveries: [...new Map(discoveries.map(x => [x.url, x])).values()] };
}

export function startRedditMonitor({ subreddit, onDiscover, intervalMs = 15 * 60 * 1000 }) {
  const run = async () => {
    try {
      const result = await scanSubreddit(subreddit);
      for (const item of result.discoveries) {
        const key = `${subreddit}|${item.url}`;
        if (seen.has(key)) continue;
        seen.set(key, Date.now());
        await onDiscover(item);
      }
    } catch (e) { console.error('XSportsX Reddit monitor:', e.message); }
  };
  run();
  return setInterval(run, Math.max(intervalMs, 5 * 60 * 1000));
}
