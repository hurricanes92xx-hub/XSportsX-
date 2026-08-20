import http from "node:http";
import { spawn } from "node:child_process";

const PORT = Number(process.env.PORT || 7000);
const UPSTREAM_PORT = Number(process.env.XSPORTSX_GATEWAY_PORT || 7002);
const BACKEND_PORT = Number(process.env.XSPORTSX_BACKEND_PORT || 7001);
const BASE = process.env.BASE_URL || "https://xsportsx.onrender.com";
const VERSION = "4.4.3";
const ADDON_ID = "com.xsportsx.sports.epg.v443";
const PREFIX = "/v443";

spawn(process.execPath, ["gateway.js"], { env: { ...process.env, PORT: String(UPSTREAM_PORT), XSPORTSX_BACKEND_PORT: String(BACKEND_PORT) }, stdio: "inherit" });

const leagueConfigs = [
  ["nfl", "NFL", "football", "nfl"],
  ["ncaaf", "NCAA Football", "football", "college-football"],
  ["nba", "NBA", "basketball", "nba"],
  ["nhl", "NHL", "hockey", "nhl"],
  ["mlb", "MLB", "baseball", "mlb"],
  ["soccer", "Soccer", "soccer", "eng.1"],
];
const LEAGUES = new Set(leagueConfigs.map(x => x[0]));
let cache = { at: 0, metas: [] };

function json(res, body, status = 200) {
  res.writeHead(status, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store, no-cache, max-age=0, must-revalidate", pragma: "no-cache", expires: "0", "access-control-allow-origin": "*", "x-xsportsx-version": VERSION, "x-xsportsx-addon-id": ADDON_ID });
  res.end(JSON.stringify(body));
}
function text(m) { return `${m.name || ""} ${m.description || ""} ${(m.genres || []).join(" ")}`.toLowerCase(); }
function classify(m) { const t = text(m); return { t, league: m.__xsportsLeague || "", live: /(^|\W)live(\W|$)|🔴/.test(t), soon: /starting soon|⏰/.test(t) }; }
function normalizeMeta(m, league) {
  const id = String(m.id || `sport:${league}-${Math.random().toString(36).slice(2)}`);
  return { ...m, id: id.startsWith("sport:") ? id : `sport:${id}`, type: "channel", posterShape: "landscape", __xsportsLeague: league, genres: [...new Set([...(m.genres || []), "Sports", league.toUpperCase()])], behaviorHints: { ...(m.behaviorHints || {}) } };
}
function validForLeague(m, league) {
  const t = text(m);
  if (league === "nfl") return /\bnfl\b|national football league/.test(t) && !/college|ncaa|cfb|ncaaf/.test(t);
  if (league === "ncaaf") return /ncaa|college football|cfb|ncaaf/.test(t) && !/nfl\b|national football league/.test(t);
  if (league === "nba") return /\bnba\b|national basketball association/.test(t) && !/ncaa|college/.test(t);
  if (league === "nhl") return /\bnhl\b|national hockey league/.test(t) && !/ncaa|college/.test(t);
  if (league === "mlb") return /\bmlb\b|major league baseball/.test(t) && !/college|ncaa/.test(t);
  if (league === "soccer") return /soccer|premier league|mls|la liga|bundesliga|serie a|ligue 1|champions league|uefa/.test(t);
  return false;
}
async function getJson(url) { const r = await fetch(url, { headers: { accept: "application/json" } }); if (!r.ok) throw new Error(String(r.status)); return r.json(); }
async function loadUpstream() {
  const now = Date.now();
  if (now - cache.at < 30000 && cache.metas.length) return cache.metas;
  const out = [];
  for (const [id, name, sport, espnLeague] of leagueConfigs) {
    // Never use a generic upcoming catalog as a substitute for a league catalog.
    // That was allowing one league's events to be stamped with another league.
    let data = null;
    try {
      data = await getJson(`http://127.0.0.1:${UPSTREAM_PORT}/catalog/sport/${id}.json`);
      if (Array.isArray(data?.metas)) {
        for (const m of data.metas) if (validForLeague(m, id)) out.push(normalizeMeta(m, id));
      }
    } catch {}
    if (data?.metas?.some(m => validForLeague(m, id))) continue;
    try {
      const e = await getJson(`https://site.api.espn.com/apis/site/v2/sports/${sport}/${espnLeague}/scoreboard?limit=100`);
      for (const ev of e.events || []) {
        const comp = ev.competitions?.[0]; const teams = comp?.competitors || [];
        const a = teams.find(x => x.homeAway === "home")?.team?.displayName || teams[0]?.team?.displayName || "TBD";
        const b = teams.find(x => x.homeAway === "away")?.team?.displayName || teams[1]?.team?.displayName || "TBD";
        const status = comp?.status?.type?.shortDetail || comp?.status?.type?.detail || "Scheduled";
        const state = comp?.status?.type?.state;
        const poster = teams[0]?.team?.logo || "https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png";
        out.push(normalizeMeta({ id: `sport:espn-${id}-${ev.id}`, type: "channel", name: `${a} vs ${b}`, poster, background: poster, description: `${name}\n${status}\n${ev.date || ""}`, releaseInfo: ev.date || "", genres: ["Sports", name, state === "in" ? "LIVE" : "Scheduled"] }, id));
      }
    } catch {}
  }
  const unique = [...new Map(out.map(m => [m.id, m])).values()];
  cache = { at: now, metas: unique };
  return unique;
}
function filtered(metas, mode) {
  if (mode === "all") return metas;
  if (LEAGUES.has(mode)) return metas.filter(m => classify(m).league === mode);
  if (mode === "live-now") return metas.filter(m => classify(m).live);
  if (mode === "starting-soon") return metas.filter(m => classify(m).soon);
  if (mode === "featured") return metas.filter(m => { const c = classify(m); return c.live || c.soon || /ranked|cfp|title|playoff|championship|rivalry|ufc/.test(c.t); });
  if (mode === "ufc") return metas.filter(m => /ufc|mma/.test(c.t));
  return metas;
}
function manifest() {
  const catalogs = [["sports-command-center","🏆 XSPORTSX • SPORTS COMMAND CENTER"],["live-now","🔴 LIVE NOW"],["starting-soon","⏰ STARTING SOON"],["featured","⭐ FEATURED"],["sports-epg","📺 ALL SPORTS • EPG"],["nfl","🏈 NFL"],["ncaaf","🏈 NCAA FOOTBALL"],["nba","🏀 NBA"],["nhl","🏒 NHL"],["mlb","⚾ MLB"],["ufc","🥊 UFC COMMAND CENTER"],["soccer","⚽ SOCCER"]];
  return { id: ADDON_ID, version: VERSION, name: "XSportsX Sports Command Center", description: "Ultimate sports command center with strict league routing, live-first discovery, landscape artwork, ESPN-powered event fallback, UFC, NCAA Football, networks, EPG and stream resolution.", logo: "https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png", background: "https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png", resources: [{ name: "catalog", types: ["channel"] }, { name: "meta", types: ["channel"], idPrefixes: ["sport:"] }, { name: "stream", types: ["channel"], idPrefixes: ["sport:"] }], types: ["channel"], idPrefixes: ["sport:"], behaviorHints: { configurable: false, configurationRequired: false }, catalogs: catalogs.map(([id, name]) => ({ type: "channel", id, name, showInHome: true })), liveTv: { enabled: true, name: "XSportsX Sports Live TV", playlist: `${BASE}${PREFIX}/live-tv.m3u`, epg: `${BASE}${PREFIX}/epg.xml`, guide: `${BASE}${PREFIX}/catalog/channel/sports-command-center.json`, refreshSeconds: 60 } };
}
async function proxy(req, res, path) {
  const r = await fetch(`http://127.0.0.1:${UPSTREAM_PORT}${path}`, { method: req.method, headers: { accept: req.headers.accept || "*/*" } });
  res.writeHead(r.status, { "content-type": r.headers.get("content-type") || "application/octet-stream", "cache-control": "no-store", "access-control-allow-origin": "*" });
  res.end(Buffer.from(await r.arrayBuffer()));
}
const server = http.createServer(async (req, res) => {
  try {
    const u = new URL(req.url || "/", `http://${req.headers.host}`); const versioned = u.pathname.startsWith(PREFIX + "/"); const path = versioned ? u.pathname.slice(PREFIX.length) || "/" : u.pathname;
    if (path === "/manifest.json") return json(res, manifest());
    if (path === "/health") return json(res, { ok: true, version: VERSION, addonId: ADDON_ID, commandCenter: true, strictLeagueRouting: true });
    if (path.startsWith("/catalog/channel/")) { const id = path.slice("/catalog/channel/".length).replace(/\.json$/, ""); const metas = await loadUpstream(); return json(res, { metas: filtered(metas, id === "sports-command-center" ? "featured" : id === "sports-epg" ? "all" : id) }); }
    if (path.startsWith("/stream/channel/")) { const id = decodeURIComponent(path.slice("/stream/channel/".length).replace(/\.json$/, "")); return proxy(req, res, `/stream/sport/${encodeURIComponent(id.replace(/^sport:/, ""))}.json`); }
    if (path.startsWith("/meta/channel/")) { const id = decodeURIComponent(path.slice("/meta/channel/".length).replace(/\.json$/, "")); const metas = await loadUpstream(); const meta = metas.find(m => m.id === id) || null; return json(res, { meta }, meta ? 200 : 404); }
    if (path === "/live-tv.m3u" || path === "/epg.xml" || path === "/live-tv.json") return proxy(req, res, path);
    return proxy(req, res, u.pathname + (u.search || ""));
  } catch (e) { return json(res, { error: "XSportsX command center unavailable", detail: String(e?.message || e) }, 502); }
});
server.listen(PORT, "0.0.0.0", () => console.log(`XSportsX ${VERSION} command center listening on ${PORT}`));
