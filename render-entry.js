import http from "node:http";
import { spawn } from "node:child_process";
import { buildM3U, buildXMLTV, pickPlayableStream } from "./nuvio-live-tv.js";
import {
  xtreamConfigured, xtreamAuth, xtreamCredentialsMatch, xtreamAccountResponse,
  xtreamUnauthorizedResponse, xtreamCategories, xtreamStreams, xtreamIdMap,
  xtreamM3U, xtreamXMLTV, resolveXtreamStream
} from "./xtream-api.js";

const PORT = Number(process.env.PORT || 7000);
const GATEWAY_PORT = Number(process.env.XSPORTSX_GATEWAY_PORT || 7002);
const BACKEND_PORT = Number(process.env.XSPORTSX_BACKEND_PORT || 7001);
const BASE = process.env.BASE_URL || "https://xsportsx.onrender.com";
const VERSION = "4.3.0";
const ESPN = "https://a.espncdn.com/i/teamlogos/leagues/500/";
const manifest = {
  id: "com.xsportsx.sports.epg",
  version: VERSION,
  name: "XSportsX Sports EPG",
  description: "Unified sports EPG and Live TV source with live and upcoming games, broadcast networks, UFC, NCAA Football, and conference network coverage.",
  logo: `${ESPN}nfl.png`,
  background: `${ESPN}nfl.png`,
  resources: [
    { name: "catalog", types: ["channel"] },
    { name: "meta", types: ["channel"], idPrefixes: ["sport:"] },
    { name: "stream", types: ["channel"], idPrefixes: ["sport:"] }
  ],
  types: ["channel"],
  idPrefixes: ["sport:"],
  behaviorHints: { configurable: false, configurationRequired: false },
  liveTv: {
    enabled: true,
    name: "XSportsX Sports Live TV",
    playlist: "/live-tv.m3u",
    epg: "/epg.xml",
    refreshSeconds: 60
  },
  catalogs: [
    { type: "channel", id: "sports-epg", name: "📺 SPORTS EPG • ALL GAMES & NETWORKS" },
    { type: "channel", id: "sports-guide", name: "🗓️ SPORTS GUIDE • NOW & NEXT" }
  ]
};

const NETWORKS = [
  ["ESPN", ["espn"]], ["ESPN2", ["espn2"]], ["ESPNU", ["espnu"]],
  ["NFL Network", ["nfl network"]], ["NHL Network", ["nhl network"]],
  ["MLB Network", ["mlb network"]], ["NBA TV", ["nba tv"]],
  ["ACC Network", ["acc network", "accn"]], ["Big Ten Network", ["big ten network", "btn"]],
  ["SEC Network", ["sec network", "secn"]], ["Big 12 Now", ["big 12 now", "big12 now"]],
  ["FOX Sports 1", ["fox sports 1", "fs1"]], ["FOX Sports 2", ["fox sports 2", "fs2"]],
  ["CBS Sports Network", ["cbs sports network", "cbssn"]], ["ABC", ["abc"]],
  ["CBS", ["cbs"]], ["FOX", ["fox"]], ["NBC", ["nbc"]], ["Peacock", ["peacock"]]
];

const gateway = (path) => fetch(`http://127.0.0.1:${GATEWAY_PORT}${path}`).then(async r => {
  if (!r.ok) throw new Error(`gateway ${r.status}`);
  return r.json();
});

function networkFor(meta) {
  const text = [meta?.name, meta?.description, ...(meta?.genres || [])].join(" ").toLowerCase();
  return NETWORKS.find(([, aliases]) => aliases.some(a => text.includes(a)))?.[0] || null;
}

function normalizeMeta(meta) {
  if (!meta || typeof meta !== "object") return meta;
  const network = networkFor(meta);
  const poster = meta.poster || meta.background || `${ESPN}nfl.png`;
  return {
    ...meta,
    type: "channel",
    poster,
    background: meta.background || poster,
    logo: meta.logo || poster,
    posterShape: "landscape",
    name: network ? `📡 ${network} • ${meta.name || "Sports Event"}` : meta.name,
    description: [network ? `📡 ${network}` : "📡 Network TBD", meta.description].filter(Boolean).join("\n\n"),
    genres: [...new Set([...(meta.genres || []), "Sports EPG", network].filter(Boolean))]
  };
}

async function sportsEpgCatalog() {
  const feeds = await Promise.all([
    gateway("/catalog/sport/upcoming.json").catch(() => ({ metas: [] })),
    gateway("/catalog/sport/live-now.json").catch(() => ({ metas: [] })),
    gateway("/catalog/sport/starting-soon.json").catch(() => ({ metas: [] })),
    gateway("/catalog/sport/cfp-watch.json").catch(() => ({ metas: [] }))
  ]);
  const byId = new Map();
  for (const feed of feeds) for (const meta of feed.metas || []) if (meta?.id) byId.set(meta.id, normalizeMeta(meta));
  const metas = [...byId.values()];
  metas.sort((a, b) => {
    const al = String(a.name || "").includes("LIVE");
    const bl = String(b.name || "").includes("LIVE");
    if (al !== bl) return al ? -1 : 1;
    return String(a.name || "").localeCompare(String(b.name || ""));
  });
  return { metas: metas.slice(0, 500) };
}

async function sportsGuideCatalog() {
  const { metas } = await sportsEpgCatalog();
  const now = Date.now();
  return {
    metas: metas.map((meta, index) => ({
      ...meta,
      id: meta.id?.startsWith("sport:") ? meta.id : `sport:${meta.id || `guide-${index}`}`,
      type: "channel",
      name: `🗓️ ${meta.name || "Sports Event"}`,
      description: `${meta.description || "Live sports event"}\n\nSPORTS GUIDE • ${new Date(now).toLocaleString()}`,
      genres: [...new Set([...(meta.genres || []), "Sports Guide", "EPG"])],
      posterShape: "landscape"
    }))
  };
}

function send(res, status, value) {
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store, no-cache, max-age=0, must-revalidate",
    "pragma": "no-cache",
    "expires": "0",
    "access-control-allow-origin": "*",
    "x-xsportsx-version": VERSION,
    "x-xsportsx-addon-id": manifest.id
  });
  res.end(JSON.stringify(value));
}

function sendText(res, status, contentType, body, cache = "no-store") {
  res.writeHead(status, {
    "content-type": contentType,
    "cache-control": cache,
    "access-control-allow-origin": "*",
    "x-xsportsx-version": VERSION,
    "x-xsportsx-addon-id": manifest.id
  });
  res.end(body);
}

async function resolvePlayable(req, res, rawId) {
  const id = decodeURIComponent(rawId || "");
  const backendId = id.replace(/^sport:/, "");
  try {
    const payload = await gateway(`/stream/sport/${encodeURIComponent(backendId)}.json`);
    const stream = pickPlayableStream(payload);
    const url = stream?.url || stream?.streamUrl;
    if (!url) return send(res, 404, { error: "No direct authorized stream URL is available for this event." });
    res.writeHead(302, { location: url, "cache-control": "no-store", "access-control-allow-origin": "*", "x-xsportsx-version": VERSION });
    res.end();
  } catch (error) { send(res, 502, { error: "stream resolution failed", detail: String(error?.message || error) }); }
}

function xtreamGuard(reqUrl) {
  const { username, password } = xtreamAuth(reqUrl);
  return xtreamCredentialsMatch(username, password) ? { username, password } : null;
}
function xtreamAuthResponse(res) {
  if (!xtreamConfigured()) return send(res, 503, { user_info: { auth: 0, status: "Not configured" }, server_info: {} });
  return send(res, 200, xtreamAccountResponse());
}
async function xtreamPlayerApi(req, res, url) {
  if (!xtreamConfigured()) return send(res, 503, { user_info: { auth: 0, status: "Not configured" }, server_info: {} });
  const auth = xtreamGuard(url.toString());
  if (!auth) return send(res, 401, xtreamUnauthorizedResponse().body);
  const action = url.searchParams.get("action") || "";
  const { metas } = await sportsEpgCatalog();
  const streams = xtreamStreams(metas), categories = xtreamCategories(metas);
  if (!action) return send(res, 200, xtreamAccountResponse());
  if (action === "get_live_categories") return send(res, 200, categories);
  if (action === "get_live_streams") {
    const categoryId = url.searchParams.get("category_id");
    return send(res, 200, categoryId ? streams.filter(s => String(s.category_id) === String(categoryId)) : streams);
  }
  if (action === "get_short_epg" || action === "get_simple_data_table") {
    const streamId = String(url.searchParams.get("stream_id") || ""), meta = xtreamIdMap(metas).get(streamId);
    if (!meta) return send(res, 200, { epg_listings: [] });
    const raw = meta?.videos?.[0]?.released || meta?.released || meta?.date || meta?.releaseInfo;
    const start = raw && Number.isFinite(Date.parse(raw)) ? new Date(raw) : new Date(), stop = new Date(start.getTime() + 3 * 60 * 60 * 1000);
    const startTimestamp = Math.floor(start.getTime() / 1000), stopTimestamp = Math.floor(stop.getTime() / 1000);
    return send(res, 200, { epg_listings: [{ id: streamId, epg_id: streamId, title: String(meta.name || "Sports Event"), lang: "en", start: start.toISOString().slice(0, 19).replace("T", " "), end: stop.toISOString().slice(0, 19).replace("T", " "), description: String(meta.description || "Live sports event"), channel_id: String(meta.id), start_timestamp: startTimestamp, stop_timestamp: stopTimestamp, now_playing: startTimestamp <= Math.floor(Date.now() / 1000) && Math.floor(Date.now() / 1000) < stopTimestamp ? 1 : 0, has_archive: 0 }] });
  }
  if (action === "get_account_info") return send(res, 200, xtreamAccountResponse().user_info);
  if (action === "get_server_info") return send(res, 200, xtreamAccountResponse().server_info);
  return send(res, 200, []);
}
async function xtreamLiveRoute(req, res, url) {
  if (!xtreamConfigured()) return send(res, 503, { error: "Xtream compatibility is not configured on this deployment." });
  const parts = url.pathname.split("/").filter(Boolean);
  if (parts.length < 4) return send(res, 404, { error: "Invalid Xtream live stream path." });
  const [, username, password, filename] = parts;
  if (!xtreamCredentialsMatch(decodeURIComponent(username), decodeURIComponent(password))) return send(res, 401, { error: "Unauthorized" });
  const streamId = filename.replace(/\.(?:ts|m3u8)$/i, ""), { metas } = await sportsEpgCatalog(), meta = xtreamIdMap(metas).get(streamId);
  if (!meta) return send(res, 404, { error: "Stream not found" });
  try {
    const stream = await resolveXtreamStream(meta, gateway), target = stream?.url || stream?.streamUrl;
    if (!target) return send(res, 404, { error: "No authorized stream is currently available." });
    res.writeHead(302, { location: target, "cache-control": "no-store", "access-control-allow-origin": "*", "x-xsportsx-version": VERSION }); res.end();
  } catch (error) { send(res, 502, { error: "stream resolution failed", detail: String(error?.message || error) }); }
}

const child = spawn(process.execPath, ["gateway.js"], { env: { ...process.env, PORT: String(GATEWAY_PORT), XSPORTSX_BACKEND_PORT: String(BACKEND_PORT) }, stdio: "inherit" });
child.on("exit", code => { if (code && code !== 0) process.exitCode = code; });

async function proxy(req, res) {
  const original = req.url || "/", path = original.split("?")[0], url = new URL(original, BASE);
  if (path === "/manifest.json" || path === "/manifest-4.3.0.json") return send(res, 200, manifest);
  if (path === "/health") return send(res, 200, { ok: true, version: VERSION, addonId: manifest.id, type: "channel", liveTv: true, xtream: xtreamConfigured() });
  if (path === "/live-tv.json") return send(res, 200, { id: manifest.id, version: VERSION, name: manifest.liveTv.name, playlist: `${BASE}${manifest.liveTv.playlist}`, epg: `${BASE}${manifest.liveTv.epg}`, refreshSeconds: manifest.liveTv.refreshSeconds, catalog: `${BASE}/catalog/channel/sports-epg.json`, guide: `${BASE}/catalog/channel/sports-guide.json`, xtream: xtreamConfigured() ? { server: BASE, playerApi: `${BASE}/player_api.php`, playlist: `${BASE}/get.php`, epg: `${BASE}/xmltv.php` } : null });
  if (path === "/player_api.php") return xtreamPlayerApi(req, res, url);
  if (path === "/xmltv.php") {
    if (!xtreamConfigured()) return sendText(res, 503, "application/xml; charset=utf-8", "<?xml version=\"1.0\" encoding=\"UTF-8\"?><tv><error>Xtream compatibility is not configured.</error></tv>");
    if (!xtreamGuard(url.toString())) return sendText(res, 401, "application/xml; charset=utf-8", "<?xml version=\"1.0\" encoding=\"UTF-8\"?><tv><error>Unauthorized</error></tv>");
    const { metas } = await sportsEpgCatalog(); return sendText(res, 200, "application/xml; charset=utf-8", xtreamXMLTV(metas));
  }
  if (path === "/get.php") {
    if (!xtreamConfigured()) return sendText(res, 503, "text/plain; charset=utf-8", "Xtream compatibility is not configured.");
    if (!xtreamGuard(url.toString())) return sendText(res, 401, "text/plain; charset=utf-8", "Unauthorized");
    const { metas } = await sportsEpgCatalog(), output = url.searchParams.get("output") === "m3u8" ? "m3u8" : "ts";
    return sendText(res, 200, "application/x-mpegURL; charset=utf-8", xtreamM3U(metas, output));
  }
  if (path.startsWith("/live/")) return xtreamLiveRoute(req, res, url);
  if (path === "/catalog/channel/sports-epg.json") return send(res, 200, await sportsEpgCatalog());
  if (path === "/catalog/channel/sports-guide.json") return send(res, 200, await sportsGuideCatalog());
  if (path === "/live-tv.m3u" || path === "/sports.m3u") { const { metas } = await sportsEpgCatalog(); return sendText(res, 200, "application/x-mpegURL; charset=utf-8", buildM3U(metas, BASE)); }
  if (path === "/epg.xml" || path === "/sports.xml" || path === "/live-tv.xml") { const { metas } = await sportsEpgCatalog(); return sendText(res, 200, "application/xml; charset=utf-8", buildXMLTV(metas)); }
  if (path.startsWith("/play/")) return resolvePlayable(req, res, path.slice("/play/".length));
  const translated = original.replace(/^\/catalog\/channel\//, "/catalog/sport/").replace(/^\/meta\/channel\//, "/meta\/sport\/").replace(/^\/stream\/channel\//, "/stream\/sport\/");
  try {
    const upstream = await fetch(`http://127.0.0.1:${GATEWAY_PORT}${translated}`, { method: req.method, headers: { ...req.headers, host: `127.0.0.1:${GATEWAY_PORT}` }, body: req.method === "GET" || req.method === "HEAD" ? undefined : req });
    const contentType = upstream.headers.get("content-type") || "application/json", body = Buffer.from(await upstream.arrayBuffer());
    if (contentType.includes("application/json")) { try { const payload = JSON.parse(body.toString("utf8")); if (Array.isArray(payload.metas)) payload.metas = payload.metas.map(normalizeMeta); if (payload.meta) payload.meta = normalizeMeta(payload.meta); return send(res, upstream.status, payload); } catch {} }
    res.writeHead(upstream.status, { "content-type": contentType, "cache-control": "no-store", "access-control-allow-origin": "*", "x-xsportsx-version": VERSION, "x-xsportsx-addon-id": manifest.id }); res.end(body);
  } catch (error) { send(res, 502, { error: "gateway unavailable", detail: String(error?.message || error) }); }
}

http.createServer(proxy).listen(PORT, "0.0.0.0", () => console.log(`XSportsX Sports EPG ${VERSION} (${manifest.id}) listening on ${PORT}`));
