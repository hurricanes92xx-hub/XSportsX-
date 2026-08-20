import http from "node:http";
import { spawn } from "node:child_process";

const PORT = Number(process.env.PORT || 7000);
const UPSTREAM_PORT = Number(process.env.XSPORTSX_GATEWAY_PORT || 7002);
const BACKEND_PORT = Number(process.env.XSPORTSX_BACKEND_PORT || 7001);
const BASE = process.env.BASE_URL || "https://xsportsx.onrender.com";
const VERSION = "4.4.4";
const ADDON_ID = "com.xsportsx.sports.epg.v443";
const PREFIX = "/v443";

spawn(process.execPath, ["gateway.js"], { env: { ...process.env, PORT: String(UPSTREAM_PORT), XSPORTSX_BACKEND_PORT: String(BACKEND_PORT) }, stdio: "inherit" });

const leagueConfigs = [
  ["nfl", "NFL", "football", "nfl"],
  ["ncaaf", "NCAA Football", "football", "college-football"],
  ["nba", "NBA", "basketball", "nba"],
  ["nhl", "NHL", "hockey", "nhl"],
  ["mlb", "MLB", "baseball", "mlb"],
  ["soccer", "Soccer", "soccer", "eng.1"]
];
let cache = { at: 0, metas: [] };

function json(res, body, status = 200) {
  res.writeHead(status, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store, no-cache, max-age=0, must-revalidate", pragma: "no-cache", expires: "0", "access-control-allow-origin": "*", "x-xsportsx-version": VERSION, "x-xsportsx-addon-id": ADDON_ID });
  res.end(JSON.stringify(body));
}
function text(m) { return `${m.name || ""} ${m.description || ""} ${(m.genres || []).join(" ")}`.toLowerCase(); }
function normalizeMeta(m, league) {
  const id = String(m.id || `sport:${league}-${Math.random().toString(36).slice(2)}`);
  return { ...m, id: id.startsWith("sport:") ? id : `sport:${id}`, type: "channel", posterShape: "landscape", genres: [...new Set([...(m.genres || []), "Sports", league.toUpperCase()])], behaviorHints: { ...(m.behaviorHints || {}) } };
}
async function getJson(url) { const r = await fetch(url); if (!r.ok) throw new Error(String(r.status)); return r.json(); }
async function loadUpstream() {
  const now = Date.now();
  if (now - cache.at < 30000 && cache.metas.length) return cache.metas;
  const out = [];
  for (const [id, name, sport, espnLeague] of leagueConfigs) {
    let data = null;
    try { data = await getJson(`http://127.0.0.1:${UPSTREAM_PORT}/catalog/sport/${id}.json`); } catch {}
    if (Array.isArray(data?.metas) && data.metas.length) {
      out.push(...data.metas.map(m => normalizeMeta(m, id)));
      continue;
    }
    try {
      const e = await getJson(`https://site.api.espn.com/apis/site/v2/sports/${sport}/${espnLeague}/scoreboard?limit=100`);
      for (const ev of e.events || []) {
        const comp = ev.competitions?.[0]; const teams = comp?.competitors || [];
        const home = teams.find(x => x.homeAway === "home")?.team || teams[0]?.team || {};
        const away = teams.find(x => x.homeAway === "away")?.team || teams[1]?.team || {};
        const status = comp?.status?.type?.shortDetail || comp?.status?.type?.detail || "Scheduled";
        const state = comp?.status?.type?.state;
        const poster = home.logo || away.logo || "https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png";
        out.push(normalizeMeta({ id: `sport:espn-${id}-${ev.id}`, type: "channel", name: `${away.displayName || "TBD"} vs ${home.displayName || "TBD"}`, poster, background: poster, description: `${name}\n${status}\n${ev.date || ""}`, releaseInfo: ev.date || "", genres: ["Sports", name, state === "in" ? "LIVE" : "Scheduled"] }, id));
      }
    } catch {}
  }
  const unique = [...new Map(out.map(m => [m.id, m])).values()];
  cache = { at: now, metas: unique };
  return unique;
}
function isLeague(m, mode) {
  const t = text(m);
  const genres = (m.genres || []).map(x => String(x).toLowerCase());
  const has = (...xs) => xs.some(x => t.includes(x) || genres.some(g => g === x));
  switch (mode) {
    case "nfl": return has("nfl");
    case "ncaaf": return has("ncaa football", "college football", "ncaaf", "cfb") && !has("nfl");
    case "nba": return has("nba") && !has("wnba");
    case "nhl": return has("nhl");
    case "mlb": return has("mlb");
    case "soccer": return has("soccer", "premier league", "mls", "la liga");
    case "ufc": return has("ufc", "mma");
    default: return false;
  }
}
function filtered(metas, mode) {
  if (mode === "all") return metas;
  if (["nfl","ncaaf","nba","nhl","mlb","soccer","ufc"].includes(mode)) return metas.filter(m => isLeague(m, mode));
  if (mode === "live-now") return metas.filter(m => /(^|\W)live(\W|$)|🔴/.test(text(m)));
  if (mode === "starting-soon") return metas.filter(m => /starting soon|⏰/.test(text(m)));
  if (mode === "featured") return metas.filter(m => /(^|\W)live(\W|$)|🔴|starting soon|⏰|ranked|cfp|title|playoff|championship|rivalry|ufc/.test(text(m)));
  return metas;
}
function manifest() {
  const catalogs = [["sports-command-center","🏆 XSPORTSX • SPORTS COMMAND CENTER"],["live-now","🔴 LIVE NOW"],["starting-soon","⏰ STARTING SOON"],["featured","⭐ FEATURED"],["sports-epg","📺 ALL SPORTS • EPG"],["nfl","🏈 NFL"],["ncaaf","🏈 NCAA FOOTBALL"],["nba","🏀 NBA"],["nhl","🏒 NHL"],["mlb","⚾ MLB"],["ufc","🥊 UFC COMMAND CENTER"],["soccer","⚽ SOCCER"]];
  return { id: ADDON_ID, version: VERSION, name: "XSportsX Sports Command Center", description: "Ultimate sports command center with strict league routing and ESPN-powered event fallback.", logo: "https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png", background: "https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png", resources: [{ name: "catalog", types: ["channel"] }, { name: "meta", types: ["channel"], idPrefixes: ["sport:"] }, { name: "stream", types: ["channel"], idPrefixes: ["sport:"] }], types: ["channel"], idPrefixes: ["sport:"], behaviorHints: { configurable: false, configurationRequired: false }, catalogs: catalogs.map(([id, name]) => ({ type: "channel", id, name, showInHome: true })), liveTv: { enabled: true, name: "XSportsX Sports Live TV", playlist: `${BASE}${PREFIX}/live-tv.m3u`, epg: `${BASE}${PREFIX}/epg.xml`, guide: `${BASE}${PREFIX}/catalog/channel/sports-command-center.json`, refreshSeconds: 60 } };
}
async function proxy(req, res, path) {
  const r = await fetch(`http://127.0.0.1:${UPSTREAM_PORT}${path}`, { method: req.method, headers: { accept: req.headers.accept || "*/*" } });
  const type = r.headers.get("content-type") || "application/octet-stream"; res.writeHead(r.status, { "content-type": type, "cache-control": "no-store", "access-control-allow-origin": "*" }); res.end(Buffer.from(await r.arrayBuffer()));
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
