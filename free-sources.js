import { TTLCache, CircuitBreaker, fetchText } from "./core.js";

const cache = new TTLCache();
const breakers = new CircuitBreaker({ failureThreshold: 3, cooldownMs: 60000 });
const timeout = Number(process.env.REQUEST_TIMEOUT_MS || 9000);

function readJson(key, fallback) {
  try { return JSON.parse(process.env[key] || JSON.stringify(fallback)); }
  catch { return fallback; }
}

// Public/official pages only. Returns watch-page links, not hidden media URLs or third-party mirrors.
const sources = readJson("FREE_OFFICIAL_SOURCES", []);

function normalize(v = "") { return String(v).toLowerCase().replace(/[^a-z0-9]+/g, " ").trim(); }
function matchesSource(source, event) {
  if (!source?.url || !event) return false;
  const sport = normalize(event.sport);
  const league = normalize(event.league);
  const title = normalize(event.title);
  const sports = (source.sports || []).map(normalize);
  const leagues = (source.leagues || []).map(normalize);
  const keywords = (source.keywords || []).map(normalize);
  if (sports.length && !sports.includes(sport)) return false;
  if (leagues.length && !leagues.some(x => league.includes(x))) return false;
  if (keywords.length && !keywords.some(x => title.includes(x) || league.includes(x))) return false;
  return true;
}

function extractCanonical(html, fallback) {
  const match = String(html || "").match(/<link[^>]+rel=["']canonical["'][^>]+href=["']([^"']+)["'][^>]*>/i)
    || String(html || "").match(/<meta[^>]+property=["']og:url["'][^>]+content=["']([^"']+)["'][^>]*>/i);
  return match?.[1] || fallback;
}

export async function freeOfficialLinksForEvent(event) {
  const out = [];
  for (const source of sources) {
    if (!matchesSource(source, event)) continue;
    const key = `free:${source.name || source.url}:${event.eventId}`;
    const cached = cache.get(key);
    if (cached) { out.push(cached); continue; }
    const breakerKey = `free:${source.name || source.url}`;
    if (breakers.isOpen(breakerKey)) continue;
    try {
      const html = await fetchText(source.url, { headers: source.headers || {} }, timeout);
      const url = extractCanonical(html, source.url);
      const item = {
        name: `🆓 ${source.name || "Official Free Watch"}`,
        externalUrl: url,
        description: source.description || "Public/official watch page",
        score: 70,
        priority: Number(source.priority || 0),
        source: "free-official"
      };
      breakers.success(breakerKey);
      cache.set(key, item, Number(source.ttlMs || 300000));
      out.push(item);
    } catch {
      breakers.failure(breakerKey);
    }
  }
  return out;
}

export function freeSourceStatus() {
  return { configured: sources.length, names: sources.map(x => x.name || x.url).filter(Boolean) };
}
