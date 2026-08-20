import http from "node:http";
import crypto from "node:crypto";

const PORT = Number(process.env.PORT || 7099);
const BASE = process.env.BASE_URL || "https://xsportsx.onrender.com";
const VERSION = "5.0.0";
const ADDON_ID = "com.xsportsx.sports.epg.v500";
const PREFIX = "/v458";
const SECRET = process.env.XSPORTSX_CONFIG_SECRET || crypto.randomBytes(32).toString("hex");
const KEY = crypto.createHash("sha256").update(SECRET).digest();

const LEAGUES = {
  nfl: ["NFL", "football", "nfl", "🏈"],
  ncaaf: ["NCAA Football", "football", "college-football", "🏈"],
  nba: ["NBA", "basketball", "nba", "🏀"],
  nhl: ["NHL", "hockey", "nhl", "🏒"],
  mlb: ["MLB", "baseball", "mlb", "⚾"],
  soccer: ["Soccer", "soccer", "eng.1", "⚽"],
  mls: ["MLS", "soccer", "usa.1", "⚽"],
  "premier-league": ["Premier League", "soccer", "eng.1", "⚽"],
  "la-liga": ["La Liga", "soccer", "esp.1", "⚽"],
  ufc: ["UFC", "mma", "ufc", "🥊"]
};

const NEWS = [
  "ESPN", "ESPN2", "ESPNU", "ESPN News", "ESPN Deportes", "NFL Network", "MLB Network",
  "NBA TV", "NHL Network", "CBS Sports", "CBS Sports Network", "Fox Sports", "FS1", "FS2",
  "ACC Network", "SEC Network", "Big Ten Network", "Golf Channel", "TNT Sports", "NBC Sports",
  "beIN Sports", "Sportsnet", "Tennis Channel"
];

const cache = new Map();
const eventCache = new Map();
const xtreamCache = new Map();

function json(res, body, status = 200, maxAge = 0) {
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": maxAge ? `public,max-age=${maxAge},stale-while-revalidate=30` : "no-store",
    "access-control-allow-origin": "*",
    "x-xsportsx-version": VERSION,
    "x-xsportsx-addon-id": ADDON_ID
  });
  res.end(JSON.stringify(body));
}
function clean(v = "") { return String(v).replace(/\s+/g, " ").trim(); }
function norm(v = "") { return clean(v).toLowerCase().replace(/[^a-z0-9]+/g, " ").trim(); }
function esc(v = "") { return String(v).replace(/[&<>\"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[c])); }
function encryptConfig(v) {
  const iv = crypto.randomBytes(12), c = crypto.createCipheriv("aes-256-gcm", KEY, iv);
  const data = Buffer.concat([c.update(JSON.stringify(v), "utf8"), c.final()]);
  return Buffer.concat([iv, c.getAuthTag(), data]).toString("base64url");
}
function decryptConfig(token) {
  if (!token) return null;
  try {
    const raw = Buffer.from(token, "base64url");
    if (raw.length < 29) return null;
    const d = crypto.createDecipheriv("aes-256-gcm", KEY, raw.subarray(0, 12));
    d.setAuthTag(raw.subarray(12, 28));
    const v = JSON.parse(Buffer.concat([d.update(raw.subarray(28)), d.final()]).toString("utf8"));
    if (!v?.server || !v?.username || !v?.password) return null;
    return { server: String(v.server).replace(/\/+$/, ""), username: String(v.username), password: String(v.password) };
  } catch { return null; }
}
function configFrom(reqUrl) { return decryptConfig(new URL(reqUrl, "http://localhost").searchParams.get("config")); }
async function getJson(url) {
  const r = await fetch(url, { headers: { accept: "application/json", "user-agent": `XSportsX/${VERSION}` } });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}
function leagueUrl(id) {
  const [, sport, espn] = LEAGUES[id];
  return `https://site.api.espn.com/apis/site/v2/sports/${sport}/${espn}/scoreboard?limit=100`;
}
function team(t = {}) { return { id: String(t.id || ""), name: t.displayName || t.name || "", short: t.abbreviation || "", logo: t.logo || t.logos?.[0]?.href || "" }; }
function eventMeta(ev, league) {
  const [name,,,icon] = LEAGUES[league], c = ev?.competitions?.[0], teams = c?.competitors || [];
  const h = teams.find(x => x.homeAway === "home")?.team || teams[0]?.team || {};
  const a = teams.find(x => x.homeAway === "away")?.team || teams[1]?.team || {};
  if (!h?.displayName && !a?.displayName) return null;
  const state = c?.status?.type?.state || "pre", detail = c?.status?.type?.shortDetail || c?.status?.type?.detail || "Scheduled";
  const id = `sport:${ev.id}`, start = ev.date || c?.date || "";
  const meta = {
    id, type: "channel", name: `${a.displayName || "TBD"} vs ${h.displayName || "TBD"}`,
    poster: h.logo || h.logos?.[0]?.href || a.logo || a.logos?.[0]?.href || undefined,
    background: h.logo || a.logo || undefined,
    description: `${icon} ${name}\n${detail}\n${start}`, releaseInfo: start,
    genres: ["Sports", name, state === "in" ? "LIVE" : "Scheduled"],
    sportSource: league, eventSport: league, league, eventId: String(ev.id),
    event: { id: String(ev.id), league, start, state, home: team(h), away: team(a), broadcast: (c?.broadcasts || []).flatMap(x => x.names || []) }
  };
  eventCache.set(id, meta);
  return meta;
}
async function leagueCatalog(id) {
  const now = Date.now(), key = `league:${id}`, hit = cache.get(key);
  if (hit && now - hit.at < 15000) return hit.value;
  const d = await getJson(leagueUrl(id));
  const metas = (d.events || []).map(e => eventMeta(e, id)).filter(Boolean).sort((a, b) => new Date(a.releaseInfo || 0) - new Date(b.releaseInfo || 0));
  cache.set(key, { at: now, value: metas });
  return metas;
}
async function allSports() {
  const ids = ["nfl", "ncaaf", "nba", "nhl", "mlb", "soccer", "ufc"];
  return (await Promise.all(ids.map(id => leagueCatalog(id).catch(() => [])))).flat();
}
function xtreamApi(c, action = "") {
  const u = new URL(`${c.server}/player_api.php`); u.searchParams.set("username", c.username); u.searchParams.set("password", c.password); if (action) u.searchParams.set("action", action); return u;
}
async function xtream(c, action = "") {
  const key = `${c.server}|${c.username}|${c.password}|${action}`, hit = xtreamCache.get(key);
  if (hit && Date.now() - hit.at < 30000) return hit.value;
  const v = await getJson(xtreamApi(c, action)); xtreamCache.set(key, { at: Date.now(), value: v }); return v;
}
function newsMatch(name, group) {
  const v = norm(`${name} ${group}`);
  if (NEWS.some(x => v.includes(norm(x)))) return 100;
  if (/\bespn\b|\bespn2\b|\bespnu\b|\bespn news\b|\bnfl network\b|\bmlb network\b|\bnba tv\b|\bnhl network\b|\bcbs sports\b|\bfox sports\b|\bfs1\b|\bfs2\b|\bacc network\b|\bsec network\b|\bbig ten network\b|\bgolf channel\b|\btnt sports\b|\bnbc sports\b|\bbein sports\b|\bsportsnet\b|\btennis channel\b/.test(v)) return 95;
  if (/\bsports?\b|sports news|sports network|live sports/.test(v)) return 75;
  return 0;
}
async function xtreamData(c) {
  if (!c) return { metas: [], news: [], categories: [] };
  const cats = await xtream(c, "get_live_categories").catch(() => []), streams = await xtream(c, "get_live_streams").catch(() => []);
  const cm = new Map((Array.isArray(cats) ? cats : []).map(x => [String(x.category_id), x.category_name || "Live TV"]));
  const metas = (Array.isArray(streams) ? streams : []).map(s => {
    const cat = cm.get(String(s.category_id)) || "Live TV", ext = String(s.container_extension || "ts").replace(/[^a-z0-9]/gi, "") || "ts";
    return { id: `xtream:${s.stream_id}`, type: "channel", name: s.name || `Channel ${s.stream_id}`, poster: s.stream_icon || undefined, background: s.stream_icon || undefined, description: `📺 ${cat}`, genres: ["IPTV", "Live TV", cat], behaviorHints: { isLive: true }, xtream: { streamUrl: `${c.server}/live/${encodeURIComponent(c.username)}/${encodeURIComponent(c.password)}/${encodeURIComponent(s.stream_id)}.${ext}`, category: cat } };
  });
  const news = metas.filter((m, i) => newsMatch(streams[i]?.name, cm.get(String(streams[i]?.category_id)) || "") >= 75);
  return { metas, news, categories: [...cm.values()] };
}
function matchEventChannel(ch, e) {
  const t = norm(`${ch.name} ${ch.group}`), a = norm(e?.away?.name), h = norm(e?.home?.name), as = norm(e?.away?.short), hs = norm(e?.home?.short);
  let score = 0; for (const x of [a, h]) if (x && t.includes(x)) score += 45; for (const x of [as, hs]) if (x && x.length >= 3 && t.includes(x)) score += 15; if (norm(ch.group).includes(norm(e?.league))) score += 10; return Math.min(score, 100);
}
async function streamsForEvent(c, meta) {
  if (!c || !meta?.event) return [];
  const d = await xtreamData(c), matches = d.metas.map(m => ({ m, score: matchEventChannel(m, meta.event) })).filter(x => x.score >= 40).sort((a, b) => b.score - a.score).slice(0, 8);
  return matches.map(x => ({ name: `▶ ${x.m.name}`, url: x.m.xtream.streamUrl, title: x.m.name, description: `${x.m.xtream.category} • match ${x.score}%`, score: x.score }));
}
function manifest() {
  const catalogs = [["sports-command-center", "🏆 XSPORTSX • SPORTS COMMAND CENTER"], ["live-now", "🔴 LIVE NOW"], ["starting-soon", "⏰ STARTING SOON"], ["featured", "⭐ FEATURED"], ["sports-news", "📰 SPORTS NEWS NETWORKS"], ["sports-epg", "📺 ALL SPORTS • EPG"], ["nfl", "🏈 NFL"], ["ncaaf", "🏈 NCAA FOOTBALL"], ["nba", "🏀 NBA"], ["nhl", "🏒 NHL"], ["mlb", "⚾ MLB"], ["ufc", "🥊 UFC COMMAND CENTER"], ["soccer", "⚽ SOCCER"], ["iptv-live", "📡 MY IPTV • LIVE TV"]];
  return { id: ADDON_ID, version: VERSION, name: "XSportsX Sports Command Center", description: "Clean league-isolated sports EPG with Xtream sports-news and live streams.", config: [{ key: "server", type: "text", title: "Xtream Server URL" }, { key: "username", type: "text", title: "Xtream Username" }, { key: "password", type: "password", title: "Xtream Password" }], behaviorHints: { configurable: true, configurationRequired: false, configurationURL: `${BASE}${PREFIX}/configure` }, resources: [{ name: "catalog", types: ["channel"] }, { name: "meta", types: ["channel"], idPrefixes: ["sport:", "xtream:"] }, { name: "stream", types: ["channel"], idPrefixes: ["sport:", "xtream:"] }], types: ["channel"], idPrefixes: ["sport:", "xtream:"], catalogs: catalogs.map(([id, name]) => ({ type: "channel", id, name, showInHome: true })) };
}
function configurePage() { return `<!doctype html><html><head><meta name="viewport" content="width=device-width"><title>XSportsX</title><style>body{margin:0;background:#08090c;color:#fff;font:16px system-ui;display:grid;place-items:center;min-height:100vh}main{width:min(520px,92vw);background:#12151b;padding:28px;border-radius:18px}label{display:block;margin:15px 0 7px}input{width:100%;box-sizing:border-box;padding:13px;border-radius:9px;border:1px solid #343a46;background:#090b10;color:#fff}button{width:100%;padding:14px;margin-top:20px;border:0;border-radius:9px;background:#e21d2d;color:#fff;font-weight:700}</style></head><body><main><h1>🏆 XSportsX</h1><p>Enter your authorized Xtream credentials. The generated manifest uses an encrypted configuration token.</p><form method="post" action="${PREFIX}/configure"><label>Server URL</label><input name="server" required placeholder="https://provider.example:8080"><label>Username</label><input name="username" required><label>Password</label><input name="password" type="password" required><button>GENERATE MANIFEST</button></form></main></body></html>`; }
function readyPage(url) { return `<!doctype html><html><body style="background:#08090c;color:#fff;font:16px system-ui;padding:30px"><h1>✅ Ready</h1><p>Copy this manifest into Nuvio.</p><input style="width:100%;padding:14px" readonly value="${esc(url)}"></body></html>`; }

const server = http.createServer(async (req, res) => {
  try {
    const u = new URL(req.url || "/", "http://localhost"), path = u.pathname, c = configFrom(req.url || "/");
    if (path === "/manifest.json") return json(res, manifest(), 200, 60);
    if (path === "/health") return json(res, { ok: true, version: VERSION, addonId: ADDON_ID, nuvioCompatible: true });
    if (path === "/configure") {
      if (req.method === "GET") { res.writeHead(200, { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" }); return res.end(configurePage()); }
      if (req.method === "POST") {
        let body = ""; for await (const chunk of req) body += chunk;
        const f = new URLSearchParams(body), cfg = { server: clean(f.get("server")).replace(/\/+$/, ""), username: clean(f.get("username")), password: String(f.get("password") || "") };
        if (!/^https?:\/\//i.test(cfg.server) || !cfg.username || !cfg.password) { res.writeHead(400); return res.end("Invalid Xtream configuration"); }
        try { const info = await xtream(cfg); if (info?.user_info?.auth !== 1) throw new Error("Xtream authentication failed"); }
        catch (e) { res.writeHead(401, { "content-type": "text/plain" }); return res.end(`Xtream login failed: ${e?.message || e}`); }
        const url = `${BASE}${PREFIX}/${encryptConfig(cfg)}/manifest.json`;
        res.writeHead(200, { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" }); return res.end(readyPage(url));
      }
      res.writeHead(405); return res.end();
    }
    if (path === "/xtream/status.json") {
      if (!c) return json(res, { configured: false, channels: 0, sportsNewsChannels: 0 });
      try { const d = await xtreamData(c); return json(res, { configured: true, channels: d.metas.length, sportsNewsChannels: d.news.length, categories: d.categories.length }); }
      catch (e) { return json(res, { configured: true, error: String(e?.message || e) }, 502); }
    }
    if (path === "/catalog/channel/sports-news.json") {
      if (!c) return json(res, { metas: [] });
      try { return json(res, { metas: (await xtreamData(c)).news }, 200, 15); } catch (e) { return json(res, { metas: [], error: String(e?.message || e) }, 502); }
    }
    if (path === "/catalog/channel/iptv-live.json") {
      if (!c) return json(res, { metas: [] });
      try { return json(res, { metas: (await xtreamData(c)).metas }, 200, 15); } catch (e) { return json(res, { metas: [], error: String(e?.message || e) }, 502); }
    }
    if (path.startsWith("/catalog/channel/")) {
      const id = path.slice("/catalog/channel/".length).replace(/\.json$/, "");
      if (id === "sports-command-center") { const ms = await allSports(); return json(res, { metas: ms.filter(m => m.event?.state === "in").slice(0, 50) }, 200, 15); }
      if (id === "live-now") { const ms = await allSports(); return json(res, { metas: ms.filter(m => m.event?.state === "in") }, 200, 15); }
      if (id === "starting-soon") { const ms = await allSports(); return json(res, { metas: ms.filter(m => m.event?.state === "pre" && new Date(m.releaseInfo) - Date.now() < 24 * 3600 * 1000) }, 200, 15); }
      if (id === "featured") { const ms = await allSports(); return json(res, { metas: ms.slice(0, 50) }, 200, 15); }
      if (id === "sports-epg") return json(res, { metas: await allSports() }, 200, 15);
      if (LEAGUES[id]) return json(res, { metas: await leagueCatalog(id) }, 200, 15);
      return json(res, { metas: [] });
    }
    if (path.startsWith("/meta/channel/")) {
      const id = decodeURIComponent(path.slice("/meta/channel/".length).replace(/\.json$/, ""));
      if (id.startsWith("xtream:")) { if (!c) return json(res, { meta: null }, 401); const d = await xtreamData(c), meta = d.metas.find(x => x.id === id); return json(res, { meta: meta || null }, meta ? 200 : 404); }
      if (id.startsWith("sport:")) { let meta = eventCache.get(id); if (!meta) { for (const lid of Object.keys(LEAGUES)) { try { const rows = await leagueCatalog(lid); meta = rows.find(x => x.id === id); if (meta) break; } catch {} } } return json(res, { meta: meta || null }, meta ? 200 : 404); }
      return json(res, { meta: null }, 404);
    }
    if (path.startsWith("/stream/channel/")) {
      const id = decodeURIComponent(path.slice("/stream/channel/".length).replace(/\.json$/, ""));
      if (id.startsWith("xtream:")) { if (!c) return json(res, { streams: [] }, 401); const d = await xtreamData(c), meta = d.metas.find(x => x.id === id); return json(res, { streams: meta?.xtream?.streamUrl ? [{ name: `▶ ${meta.name}`, url: meta.xtream.streamUrl, title: meta.name }] : [] }); }
      if (id.startsWith("sport:")) { let meta = eventCache.get(id); if (!meta) { for (const lid of Object.keys(LEAGUES)) { try { const rows = await leagueCatalog(lid); meta = rows.find(x => x.id === id); if (meta) break; } catch {} } } return json(res, { streams: await streamsForEvent(c, meta) }); }
      return json(res, { streams: [] });
    }
    return json(res, { error: "Not found" }, 404);
  } catch (e) { console.error("XSportsX router error", e); return json(res, { error: String(e?.message || e) }, 502); }
});
server.listen(PORT, "0.0.0.0", () => console.log(`XSportsX v${VERSION} router on ${PORT}`));
