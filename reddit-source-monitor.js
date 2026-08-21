import crypto from 'node:crypto';

// Credential-free Reddit discovery through the public RSS feed. Discoveries
// are sent to XSportsX's approval queue and are never activated automatically.
const UA = process.env.REDDIT_USER_AGENT || 'XSportsX public-feed source monitor/1.1';
const MAX_FETCH_BYTES = 2 * 1024 * 1024;
const FETCH_TIMEOUT_MS = 8000;
const seen = new Map();

function normalizeSubreddit(input) {
  const s = String(input || '').trim();
  const m = s.match(/(?:reddit\.com|old\.reddit\.com|www\.reddit\.com)\/r\/([A-Za-z0-9_]+)|^r\/([A-Za-z0-9_]+)$|^([A-Za-z0-9_]+)$/i);
  return m ? (m[1] || m[2] || m[3]) : null;
}
function decodeEntities(s) { return String(s || '').replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&#x27;/gi, "'"); }
function stripTags(s) { return decodeEntities(s).replace(/<br\s*\/?>(?=.)/gi, '\n').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim(); }
function tag(xml, name) { const re = new RegExp(`<${name}(?:\\s[^>]*)?>([\\s\\S]*?)<\\/${name}>`, 'i'); const m = String(xml).match(re); return m ? decodeEntities(m[1]) : ''; }
function decodeB64(value) { const s = String(value || '').replace(/\s+/g, ''); if (s.length < 24 || s.length % 4 === 1 || !/^[A-Za-z0-9+/=_-]+$/.test(s)) return null; try { const out = Buffer.from(s.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8'); if (!out || /�/.test(out)) return null; return out; } catch { return null; } }
function extractB64(text) { const hits = []; for (const p of String(text || '').match(/[A-Za-z0-9+/_=-]{32,}/g) || []) { const d = decodeB64(p); if (d && (d.includes('http://') || d.includes('https://') || d.includes('#EXTM3U') || d.includes('player_api.php') || d.includes('get.php') || d.toLowerCase().includes('stalker'))) hits.push(d); } return hits; }
function urls(text) { return [...new Set((String(text || '').match(/https?:\/\/[^\s"'<>]+/gi) || []).map(x => x.replace(/[\]\[),;]+$/g, '')))]; }
function isCredentialUrl(url) { return /(?:[?&](?:username|password|user|pass)=|player_api\.php\?)/i.test(String(url)); }
function classify(text, url) { const s = `${text}\n${url}`.toLowerCase(); if (s.includes('#extm3u') || s.includes('#extinf') || /\.(?:m3u8?|mpd)(?:$|[?#])/i.test(s)) return 'm3u'; if (s.includes('player_api.php') || s.includes('get.php') || /[?&]username=/.test(s)) return 'xtream'; if (s.includes('stalker') || s.includes('/portal.php')) return 'stalker'; return 'direct'; }
function itemsFromRss(xml) { const items = []; const blocks = String(xml).match(/<entry\b[\s\S]*?<\/entry>/gi) || String(xml).match(/<item\b[\s\S]*?<\/item>/gi) || []; for (const block of blocks) { const id = tag(block, 'id') || tag(block, 'guid') || tag(block, 'link') || crypto.createHash('sha256').update(block).digest('hex').slice(0, 24); const title = stripTags(tag(block, 'title')); const summary = stripTags(tag(block, 'content') || tag(block, 'description') || tag(block, 'summary')); const linkMatch = block.match(/<link[^>]+href=["']([^"']+)["'][^>]*>/i); const link = linkMatch ? decodeEntities(linkMatch[1]) : stripTags(tag(block, 'link')); const published = tag(block, 'published') || tag(block, 'pubDate') || tag(block, 'updated'); items.push({ id, title, text: `${title}\n${summary}\n${link}`, published, link }); } return items; }
async function fetchPublicText(url) { if (isCredentialUrl(url)) return ''; let u; try { u = new URL(url); } catch { return ''; } if (!['http:','https:'].includes(u.protocol)) return ''; const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS); try { const r = await fetch(u, { redirect: 'follow', signal: controller.signal, headers: { 'user-agent': UA, accept: 'text/plain,text/html,application/json,*/*' } }); if (!r.ok) return ''; const len = Number(r.headers.get('content-length') || 0); if (len > MAX_FETCH_BYTES) return ''; const buf = await r.arrayBuffer(); if (buf.byteLength > MAX_FETCH_BYTES) return ''; return Buffer.from(buf).toString('utf8'); } catch { return ''; } finally { clearTimeout(timer); } }
async function expandDestination(url, maxDepth = 2) { const found = new Set(); let frontier = [url]; const visited = new Set(); for (let depth = 0; depth < maxDepth && frontier.length; depth++) { const next = []; for (const item of frontier) { if (visited.has(item) || isCredentialUrl(item)) continue; visited.add(item); const text = await fetchPublicText(item); if (!text) continue; for (const u of urls(text)) { if (isCredentialUrl(u)) continue; found.add(u); if (!visited.has(u) && depth + 1 < maxDepth) next.push(u); } for (const d of extractB64(text)) for (const u of urls(d)) { if (isCredentialUrl(u)) continue; found.add(u); if (!visited.has(u) && depth + 1 < maxDepth) next.push(u); } } frontier = [...new Set(next)].slice(0, 50); } return [...found]; }

export async function scanSubreddit(input, { maxPosts = 100 } = {}) {
  const subreddit = normalizeSubreddit(input);
  if (!subreddit) throw new Error('Enter a valid subreddit URL such as https://www.reddit.com/r/example');
  const limit = Math.min(Math.max(Number(maxPosts) || 100, 1), 100);
  const endpoint = `https://www.reddit.com/r/${encodeURIComponent(subreddit)}/new/.rss?limit=${limit}`;
  const r = await fetch(endpoint, { headers: { 'user-agent': UA, accept: 'application/atom+xml, application/rss+xml, text/xml' } });
  if (!r.ok) throw new Error(`Reddit RSS returned HTTP ${r.status}`);
  const xml = await r.text();
  const posts = itemsFromRss(xml).slice(0, limit);
  const discoveries = [];
  for (const p of posts) {
    const decoded = extractB64(p.text);
    const initial = [...new Set([...urls(p.text), ...decoded.flatMap(urls)])].filter(u => !isCredentialUrl(u));
    for (const destination of initial) {
      const expanded = await expandDestination(destination, 2);
      const actual = expanded.length ? expanded : [destination];
      for (const url of actual) discoveries.push({ id: crypto.createHash('sha256').update(`${p.id}|${url}`).digest('hex').slice(0, 24), postId: p.id, title: p.title, subreddit, url, type: classify(`${p.text}\n${decoded.join('\n')}`, url), details: expanded.length ? `Decoded Reddit post → fetched destination → discovered source` : `Discovered in Reddit post ${p.id}`, discoveredAt: p.published || new Date().toISOString(), postUrl: p.link });
    }
  }
  return { subreddit, postsChecked: posts.length, discoveries: [...new Map(discoveries.map(x => [x.url, x])).values()] };
}

export function startRedditMonitor({ subreddit, onDiscover, intervalMs = 15 * 60 * 1000 }) { const run = async () => { try { const result = await scanSubreddit(subreddit); for (const item of result.discoveries) { const key = `${subreddit}|${item.url}`; if (seen.has(key)) continue; seen.set(key, Date.now()); await onDiscover(item); } } catch (e) { console.error('XSportsX Reddit RSS monitor:', e.message); } }; run(); return setInterval(run, Math.max(intervalMs, 5 * 60 * 1000)); }
