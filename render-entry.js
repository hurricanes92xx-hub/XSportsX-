import http from "node:http";
import { spawn } from "node:child_process";

const PUBLIC_PORT = Number(process.env.PORT || 7000);
const GATEWAY_PORT = Number(process.env.XSPORTSX_GATEWAY_PORT || 7002);
const BACKEND_PORT = Number(process.env.XSPORTSX_BACKEND_PORT || 7001);
const BASE = process.env.BASE_URL || `https://xsportsx.onrender.com`;
const VERSION = "3.9.7";
const RAW = "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/main/";

const ASSETS = {
  nfl:"nfl.gif", nba:"nba.gif", nhl:"nhl.gif", mlb:"mlb.gif", ncaaf:"ncaaf.gif", ncaab:"ncaab.gif",
  wnba:"wnba.gif", mls:"mls.gif", "premier-league":"premier-league.gif", "la-liga":"la-liga.gif",
  f1:"f1.gif", motogp:"motogp.gif", ufc:"ufc.gif", boxing:"boxing.gif", atp:"atp.gif", wta:"wta.gif",
  pga:"pga.gif", rugby:"rugby.gif", cricket:"cricket.gif", pdc:"pdc.gif", afl:"afl.gif"
};
const FALLBACK = `${BASE}/artwork/nfl.gif`;

const manifest = {
  id: "com.xsportsx.live",
  version: VERSION,
  name: "XSportsX",
  description: "XSportsX — cinematic, collection-first live sports hub for Nuvio.",
  logo: `${BASE}/artwork/nfl.gif`,
  background: `${BASE}/artwork/nfl.gif`,
  resources: [
    { name: "catalog", types: ["sport"], idPrefixes: ["sport:"] },
    { name: "meta", types: ["sport"], idPrefixes: ["sport:"] },
    { name: "stream", types: ["sport"], idPrefixes: ["sport:"] }
  ],
  types: ["sport"],
  idPrefixes: ["sport:"],
  behaviorHints: { configurable: true, configurationRequired: false },
  catalogs: [
    { type: "sport", id: "sports-leagues", name: "🏆 SPORTS LEAGUES" },
    { type: "sport", id: "favorite-teams", name: "⭐ FAVORITE TEAMS" },
    { type: "sport", id: "live-now", name: "🔴 LIVE NOW" },
    { type: "sport", id: "starting-soon", name: "⏰ STARTING SOON" },
    { type: "sport", id: "ufc-home", name: "🥊 UFC • FIGHT NIGHT COMMAND CENTER" },
    { type: "sport", id: "ufc", name: "🔥 UFC • FIGHT CARDS" },
    { type: "sport", id: "ufc-rankings", name: "🏆 UFC • RANKINGS" },
    { type: "sport", id: "ufc-fighters", name: "👊 UFC • FIGHTERS" },
    { type: "sport", id: "ncaaf", name: "🏈 NCAA FOOTBALL • COMMAND CENTER" },
    { type: "sport", id: "cfp-watch", name: "🏆 NCAA FOOTBALL • CFP WATCH" },
    { type: "sport", id: "sports-news", name: "📰 SPORTS NEWS • ENGLISH" },
    { type: "sport", id: "today", name: "📅 TODAY" }
  ]
};

const child = spawn(process.execPath, ["gateway.js"], {
  env: { ...process.env, PORT: String(GATEWAY_PORT), XSPORTSX_BACKEND_PORT: String(BACKEND_PORT) },
  stdio: "inherit"
});
child.on("exit", code => { if (code && code !== 0) process.exitCode = code; });

function sendJson(res, value) {
  const body = JSON.stringify(value);
  res.writeHead(200, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "access-control-allow-origin": "*" });
  res.end(body);
}

function assetForMeta(meta) {
  const hay = [meta?.id, meta?.name, meta?.description, ...(meta?.genres || [])].join(" ").toLowerCase();
  for (const [key, file] of Object.entries(ASSETS)) {
    if (hay.includes(key.replaceAll("-", " "))) return `${BASE}/artwork/${file}`;
  }
  if (hay.includes("college football")) return `${BASE}/artwork/ncaaf.gif`;
  if (hay.includes("college basketball")) return `${BASE}/artwork/ncaab.gif`;
  return FALLBACK;
}

function normalizeMeta(meta) {
  if (!meta || typeof meta !== "object") return meta;
  const fallback = assetForMeta(meta);
  const out = { ...meta };
  // Nuvio clients are most reliable when the card image is a directly fetchable HTTPS asset.
  if (!out.poster || !String(out.poster).startsWith("https://")) out.poster = fallback;
  if (!out.background || !String(out.background).startsWith("https://")) out.background = fallback;
  if (!out.logo || !String(out.logo).startsWith("https://")) out.logo = fallback;
  out.posterShape = out.posterShape || "landscape";
  if (Array.isArray(out.videos)) {
    out.videos = out.videos.map(video => ({ ...video, thumbnail: (video?.thumbnail && String(video.thumbnail).startsWith("https://")) ? video.thumbnail : fallback }));
  }
  return out;
}

function normalizePayload(payload) {
  if (!payload || typeof payload !== "object") return payload;
  if (Array.isArray(payload.metas)) return { ...payload, metas: payload.metas.map(normalizeMeta) };
  if (payload.meta) return { ...payload, meta: normalizeMeta(payload.meta) };
  return payload;
}

async function proxy(req, res) {
  const target = `http://127.0.0.1:${GATEWAY_PORT}${req.url}`;
  try {
    const headers = { ...req.headers, host: `127.0.0.1:${GATEWAY_PORT}` };
    const upstream = await fetch(target, { method: req.method, headers, body: req.method === "GET" || req.method === "HEAD" ? undefined : req });
    const contentType = upstream.headers.get("content-type") || "application/json";
    const buffer = Buffer.from(await upstream.arrayBuffer());
    if (contentType.includes("application/json")) {
      try {
        const payload = normalizePayload(JSON.parse(buffer.toString("utf8")));
        const body = Buffer.from(JSON.stringify(payload));
        res.writeHead(upstream.status, { "content-type":"application/json; charset=utf-8", "cache-control":"no-store", "access-control-allow-origin":"*" });
        return res.end(body);
      } catch (_) {}
    }
    res.writeHead(upstream.status, {
      "content-type": contentType,
      "cache-control": upstream.headers.get("cache-control") || "no-store",
      "access-control-allow-origin": "*"
    });
    res.end(buffer);
  } catch (error) {
    res.writeHead(502, { "content-type": "application/json", "access-control-allow-origin": "*" });
    res.end(JSON.stringify({ error: "gateway unavailable", detail: String(error?.message || error) }));
  }
}

async function serveArtwork(req, res) {
  const match = /^\/artwork\/([a-z0-9-]+\.gif)$/i.exec(new URL(req.url, BASE).pathname);
  if (!match) return false;
  const file = match[1];
  if (!Object.values(ASSETS).includes(file) && file !== "nfl.gif") { res.writeHead(404); res.end(); return true; }
  try {
    const upstream = await fetch(`${RAW}${file}`);
    if (!upstream.ok) { res.writeHead(404); res.end(); return true; }
    const data = Buffer.from(await upstream.arrayBuffer());
    res.writeHead(200, { "content-type":"image/gif", "cache-control":"public,max-age=86400", "access-control-allow-origin":"*" });
    res.end(data);
  } catch {
    res.writeHead(502); res.end();
  }
  return true;
}

const server = http.createServer(async (req, res) => {
  if (req.url === "/manifest.json") return sendJson(res, manifest);
  if (req.url === "/health") return sendJson(res, { ok: true, version: VERSION, gateway: GATEWAY_PORT, backend: BACKEND_PORT, baseUrl: BASE });
  if (await serveArtwork(req, res)) return;
  return proxy(req, res);
});

server.listen(PUBLIC_PORT, "0.0.0.0", () => {
  console.log(`XSportsX Render entrypoint ${VERSION} listening on ${PUBLIC_PORT}; gateway ${GATEWAY_PORT}; backend ${BACKEND_PORT}`);
});