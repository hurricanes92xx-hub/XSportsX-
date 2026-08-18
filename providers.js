import { TTLCache, CircuitBreaker, fetchJson, fetchText, matchScore, rankStreams } from "./core.js";

const cache = new TTLCache();
const breakers = new CircuitBreaker({ failureThreshold: 3, cooldownMs: 60000 });

const SPORTS = {
  nfl: ["football", "nfl"],
  nhl: ["hockey", "nhl"],
  nba: ["basketball", "nba"],
  mlb: ["baseball", "mlb"],
  ncaaf: ["football", "college-football"],
  ncaab: ["basketball", "mens-college-basketball"],
  wnba: ["basketball", "wnba"],
  mls: ["soccer", "usa.1"],
  "premier-league": ["soccer", "eng.1"],
  "la-liga": ["soccer", "esp.1"],
  ufc: ["mma", "ufc"],
  f1: ["racing", "f1"],
  motogp: ["racing", "motogp"],
  boxing: ["boxing", "boxing"],
  atp: ["tennis", "atp"],
  wta: ["tennis", "wta"],
  pga: ["golf", "pga"],
  rugby: ["rugby", "rugby"],
  cricket: ["cricket", "cricket"],
  pdc: ["darts", "darts"],
  afl: ["football", "aus.1"]
};

const sports = (process.env.SPORTS || Object.keys(SPORTS).join(",")).split(",").map(x => x.trim()).filter(Boolean);
const m3uSources = readJson("AUTHORIZED_M3U_SOURCES", []);
const xtreamSources = readJson("AUTHORIZED_XTREAM_SOURCES", []);
const directSources = readJson("AUTHORIZED_EVENT_STREAMS", []);
const jsonFeeds = readJson("AUTHORIZED_JSON_EVENT_FEEDS", []);
const officialLinks = readJson("OFFICIAL_WATCH_LINKS", {});
const timeout = Number(process.env.REQUEST_TIMEOUT_MS || 9000);

function readJson(key, fallback) {
  try { return JSON.parse(process.env[key] || JSON.stringify(fallback)); } catch { return fallback; }
}

function team(t = {}) {
  return {
    id: String(t.id || ""),
    name: t.displayName || t.name || "",
    short: t.abbreviation || t.short || "",
    logo: t.logo || t.logos?.[0]?.href || ""
  };
}

function espnEvent(e, sport) {
  const c = e?.competitions?.[0];
  if (!c) return null;
  const home = c.competitors?.find(x => x.homeAway === "home") || c.competitors?.[1];
  const away = c.competitors?.find(x => x.homeAway === "away") || c.competitors?.[0];
  if (!home || !away) return null;
  const status = c.status?.type || {};
  return {
    id: `sport:${e.id}`,
    eventId: String(e.id),
    sport,
    league: e?.league?.abbreviation || sport.toUpperCase(),
    title: `${away.team?.displayName || "Away"} vs ${home.team?.displayName || "Home"}`,
    state: status.state || "pre",
    detail: status.shortDetail || status.detail || "",
    start: e.date || c.date,
    venue: c.venue?.fullName || "",
    broadcast: (c.broadcasts || []).flatMap(x => x.names || []),
    home: team(home.team),
    away: team(away.team),
    links: e.links || []
  };
}

async function espnScoreboard(sport, date) {
  const pair = SPORTS[sport];
  if (!pair) return [];
  const key = `espn:${sport}:${date}`;
  const cached = cache.get(key);
  if (cached) return cached;
  if (breakers.isOpen(`espn:${sport}`)) return [];

  try {
    const [group, league] = pair;
    const url = `https://site.api.espn.com/apis/site/v2/sports/${group}/${league}/scoreboard?dates=${date.replaceAll("-","")}`;
    const data = await fetchJson(url, {}, timeout);
    breakers.success(`espn:${sport}`);
    return cache.set(key, (data.events || []).map(e => espnEvent(e, sport)).filter(Boolean), 60000);
  } catch (e) {
    breakers.failure(`espn:${sport}`);
    return [];
  }
}

async function jsonEventFeeds() {
  const out = [];
  for (const src of jsonFeeds) {
    if (!src?.url || breakers.isOpen(`json:${src.name || src.url}`)) continue;
    try {
      const data = await fetchJson(src.url, { headers: src.headers || {} }, timeout);
      const items = Array.isArray(data) ? data : (data.events || data.items || []);
      for (const x of items) {
        if (!x?.id || !x.home || !x.away) continue;
        out.push({
          id: `sport:${x.id}`, eventId: String(x.id),
          sport: x.sport || "other", league: x.league || src.name || "SPORTS",
          title: x.title || `${x.away.name} vs ${x.home.name}`,
          state: x.state || "pre", detail: x.detail || "", start: x.start,
          venue: x.venue || "", broadcast: x.broadcast || [],
          home: team(x.home), away: team(x.away), links: x.links || []
        });
      }
      breakers.success(`json:${src.name || src.url}`);
    } catch {
      breakers.failure(`json:${src.name || src.url}`);
    }
  }
  return out;
}

export async function getEvents({ days = 1, date = new Date() } = {}) {
  const dates = [];
  const base = new Date(date);
  for (let i = 0; i < Math.max(1, Math.min(Number(days) || 1, 7)); i++) {
    const d = new Date(base);
    d.setUTCDate(base.getUTCDate() + i);
    dates.push(d.toISOString().slice(0, 10));
  }

  const resultSets = [];
  for (const day of dates) {
    const results = await Promise.all(sports.map(s => espnScoreboard(s, day)));
    resultSets.push(...results);
  }

  const all = [...resultSets.flat(), ...(await jsonEventFeeds())];
  const unique = new Map();
  for (const e of all) unique.set(e.eventId, e);
  return [...unique.values()].sort((a,b) => new Date(a.start || 0) - new Date(b.start || 0));
}

export async function parseM3U(url) {
  const key = `m3u:${url}`;
  const cached = cache.get(key);
  if (cached) return cached;
  const text = await fetchText(url, {}, timeout);
  const lines = text.split(/\r?\n/);
  const channels = [];
  let current = null;
  for (const raw of lines) {
    const line = raw.trim();
    if (line.startsWith("#EXTINF")) {
      const attrs = {};
      for (const m of line.matchAll(/([\w-]+)="([^"]*)"/g)) attrs[m[1]] = m[2];
      current = {
        name: line.split(",").slice(1).join(",").trim(),
        group: attrs["group-title"] || "",
        id: attrs["tvg-id"] || "",
        logo: attrs["tvg-logo"] || ""
      };
    } else if (line && !line.startsWith("#") && current) {
      channels.push({...current, url: line});
      current = null;
    }
  }
  return cache.set(key, channels, 120000);
}

async function m3uStreams(event) {
  const out = [];
  for (const src of m3uSources) {
    if (!src?.url) continue;
    try {
      const channels = await parseM3U(src.url);
      const matches = channels.map(channel => ({ channel, score: matchScore(channel, event) }))
        .filter(x => x.score >= Number(src.minScore || 35))
        .sort((a,b) => b.score-a.score).slice(0, 8);
      for (const m of matches) {
        out.push({
          name: `${src.name || "Authorized IPTV"} • ${m.channel.name}`,
          url: m.channel.url,
          description: `${m.channel.group || "IPTV"} • match ${m.score}%`,
          logo: m.channel.logo || undefined,
          score: m.score,
          priority: Number(src.priority || 0),
          source: src.name || "m3u"
        });
      }
    } catch {}
  }
  return out;
}

async function xtreamStreams(event) {
  const out = [];
  for (const src of xtreamSources) {
    if (!src?.baseUrl || !src.username || !src.password) continue;
    try {
      const base = src.baseUrl.replace(/\/+$/, "");
      const api = `${base}/player_api.php?username=${encodeURIComponent(src.username)}&password=${encodeURIComponent(src.password)}`;
      const live = await fetchJson(`${api}&action=get_live_streams`, {}, timeout);
      for (const item of Array.isArray(live) ? live : []) {
        const channel = { name: item.name || "", group: item.category_name || "", id: item.stream_id || "" };
        const score = matchScore(channel, event);
        if (score < Number(src.minScore || 35)) continue;
        const ext = item.container_extension || "ts";
        out.push({
          name: `${src.name || "Authorized IPTV"} • ${channel.name}`,
          url: `${base}/live/${encodeURIComponent(src.username)}/${encodeURIComponent(src.password)}/${encodeURIComponent(item.stream_id)}.${ext}`,
          description: `${channel.group || "IPTV"} • match ${score}%`,
          logo: item.stream_icon || undefined,
          score, priority: Number(src.priority || 0),
          source: src.name || "xtream"
        });
      }
    } catch {}
  }
  return out;
}

function directStreams(event) {
  return directSources.filter(x => String(x?.eventId) === String(event.eventId) && x.url)
    .map(x => ({
      name: x.name || "Authorized direct feed",
      url: x.url,
      description: x.description || "Authorized direct stream",
      score: 100,
      priority: Number(x.priority || 100),
      source: x.name || "direct"
    }));
}

function official(event) {
  const out = [];
  for (const [label, url] of Object.entries(officialLinks)) {
    if (url && (
      event.broadcast.some(b => String(b).toLowerCase().includes(label.toLowerCase())) ||
      String(event.league).toLowerCase().includes(label.toLowerCase())
    )) {
      out.push({ name: `Official ${label}`, externalUrl: url, description: "Official watch page" });
    }
  }
  return out;
}

export async function streamsFor(event) {
  const [a,b] = await Promise.all([m3uStreams(event), xtreamStreams(event)]);
  const streams = rankStreams([...directStreams(event), ...a, ...b]);
  return [...streams.slice(0, Number(process.env.MAX_STREAMS_PER_EVENT || 12)), ...official(event)];
}

export function providerStatus() {
  return {
    espnSports: sports,
    m3uSources: m3uSources.length,
    xtreamSources: xtreamSources.length,
    directSources: directSources.length,
    jsonFeeds: jsonFeeds.length,
    circuits: breakers.status()
  };
}
