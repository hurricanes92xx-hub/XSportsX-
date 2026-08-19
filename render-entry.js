import http from "node:http";
import { spawn } from "node:child_process";
import { buildM3U, buildXMLTV, pickPlayableStream } from "./nuvio-live-tv.js";

const PORT = Number(process.env.PORT || 7000);
const GATEWAY_PORT = Number(process.env.XSPORTSX_GATEWAY_PORT || 7002);
const BACKEND_PORT = Number(process.env.XSPORTSX_BACKEND_PORT || 7001);
const BASE = process.env.BASE_URL || "https://xsportsx.onrender.com";
const VERSION = "4.2.1";
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
  catalogs: [{ type: "channel", id: "sports-epg", name: "📺 SPORTS EPG • ALL GAMES & NETWORKS" }]
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
  // Live TV should be event-driven, not dependent on a handful of specialty
  // catalogs. Pull the complete rolling event horizon plus the two high-priority
  // lanes so every league, UFC event, and NCAA event can reach the guide.
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
    res.writeHead(302, {
      location: url,
      "cache-control": "no-store",
      "access-control-allow-origin": "*",
      "x-xsportsx-version": VERSION
    });
    res.end();
  } catch (error) {
    send(res, 502, { error: "stream resolution failed", detail: String(error?.message || error) });
  }
}

const child = spawn(process.execPath, ["gateway.js"], {
  env: { ...process.env, PORT: String(GATEWAY_PORT), XSPORTSX_BACKEND_PORT: String(BACKEND_PORT) },
  stdio: "inherit"
});
child.on("exit", code => { if (code && code !== 0) process.exitCode = code; });

async function proxy(req, res) {
  const original = req.url || "/";
  const path = original.split("?")[0];

  if (path === "/manifest.json" || path === "/manifest-4.2.1.json") return send(res, 200, manifest);
  if (path === "/health") return send(res, 200, { ok: true, version: VERSION, addonId: manifest.id, type: "channel", liveTv: true });
  if (path === "/live-tv.json") return send(res, 200, {
    id: manifest.id,
    version: VERSION,
    name: manifest.liveTv.name,
    playlist: `${BASE}${manifest.liveTv.playlist}`,
    epg: `${BASE}${manifest.liveTv.epg}`,
    refreshSeconds: manifest.liveTv.refreshSeconds,
    catalog: `${BASE}/catalog/channel/sports-epg.json`
  });
  if (path === "/catalog/channel/sports-epg.json") return send(res, 200, await sportsEpgCatalog());

  if (path === "/live-tv.m3u" || path === "/sports.m3u") {
    const { metas } = await sportsEpgCatalog();
    return sendText(res, 200, "application/x-mpegURL; charset=utf-8", buildM3U(metas, BASE));
  }
  if (path === "/epg.xml" || path === "/sports.xml" || path === "/live-tv.xml") {
    const { metas } = await sportsEpgCatalog();
    return sendText(res, 200, "application/xml; charset=utf-8", buildXMLTV(metas));
  }
  if (path.startsWith("/play/")) return resolvePlayable(req, res, path.slice("/play/".length));

  const translated = original
    .replace(/^\/catalog\/channel\//, "/catalog/sport/")
    .replace(/^\/meta\/channel\//, "/meta/sport/")
    .replace(/^\/stream\/channel\//, "/stream/sport/");

  try {
    const upstream = await fetch(`http://127.0.0.1:${GATEWAY_PORT}${translated}`, {
      method: req.method,
      headers: { ...req.headers, host: `127.0.0.1:${GATEWAY_PORT}` },
      body: req.method === "GET" || req.method === "HEAD" ? undefined : req
    });
    const contentType = upstream.headers.get("content-type") || "application/json";
    const body = Buffer.from(await upstream.arrayBuffer());
    if (contentType.includes("application/json")) {
      try {
        const payload = JSON.parse(body.toString("utf8"));
        if (Array.isArray(payload.metas)) payload.metas = payload.metas.map(normalizeMeta);
        if (payload.meta) payload.meta = normalizeMeta(payload.meta);
        return send(res, upstream.status, payload);
      } catch {}
    }
    res.writeHead(upstream.status, {
      "content-type": contentType,
      "cache-control": "no-store",
      "access-control-allow-origin": "*",
      "x-xsportsx-version": VERSION,
      "x-xsportsx-addon-id": manifest.id
    });
    res.end(body);
  } catch (error) {
    send(res, 502, { error: "gateway unavailable", detail: String(error?.message || error) });
  }
}

http.createServer(proxy).listen(PORT, "0.0.0.0", () => {
  console.log(`XSportsX Sports EPG ${VERSION} (${manifest.id}) listening on ${PORT}`);
});
