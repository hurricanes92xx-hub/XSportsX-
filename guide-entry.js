import http from "node:http";
import { spawn } from "node:child_process";

const PORT = Number(process.env.PORT || 7000);
const UPSTREAM_PORT = Number(process.env.XSPORTSX_GUIDE_UPSTREAM_PORT || 7010);
const BASE = process.env.BASE_URL || "https://xsportsx.onrender.com";
const VERSION = "4.3.0";

const child = spawn(process.execPath, ["render-entry.js"], {
  env: { ...process.env, PORT: String(UPSTREAM_PORT), BASE_URL: BASE },
  stdio: "inherit"
});
child.on("exit", code => { if (code && code !== 0) process.exitCode = code; });

function send(res, status, type, body) {
  res.writeHead(status, {
    "content-type": type,
    "cache-control": "no-store, no-cache, max-age=0, must-revalidate",
    "pragma": "no-cache",
    "expires": "0",
    "access-control-allow-origin": "*",
    "x-xsportsx-version": VERSION,
    "x-xsportsx-addon-id": "com.xsportsx.sports.epg"
  });
  res.end(body);
}

async function guideCatalog() {
  const feeds = await Promise.all([
    "/catalog/channel/sports-epg.json",
    "/catalog/sport/upcoming.json",
    "/catalog/sport/live-now.json",
    "/catalog/sport/starting-soon.json",
    "/catalog/sport/cfp-watch.json"
  ].map(async path => {
    try {
      const r = await fetch(`http://127.0.0.1:${UPSTREAM_PORT}${path}`);
      return r.ok ? await r.json() : { metas: [] };
    } catch { return { metas: [] }; }
  }));
  const byId = new Map();
  for (const feed of feeds) for (const meta of feed.metas || []) if (meta?.id) byId.set(meta.id, meta);
  const now = Date.now();
  const metas = [...byId.values()].map(meta => {
    const raw = meta?.videos?.[0]?.released || meta?.released || meta?.date || meta?.releaseInfo;
    const parsed = raw ? Date.parse(raw) : NaN;
    const start = Number.isFinite(parsed) ? parsed : now;
    return {
      ...meta,
      type: "channel",
      id: String(meta.id).startsWith("sport:") ? meta.id : `sport:${meta.id}`,
      posterShape: "landscape",
      name: `🗓️ ${meta.name || "Sports Event"}`,
      description: `${meta.description || "Live sports event"}\n\nSPORTS GUIDE • ${new Date(start).toLocaleString()}`,
      genres: [...new Set([...(meta.genres || []), "Sports Guide", "EPG"])],
      _guideStart: start
    };
  }).sort((a, b) => a._guideStart - b._guideStart).slice(0, 300);
  return { metas: metas.map(({ _guideStart, ...meta }) => meta) };
}

async function proxy(req, res) {
  const original = req.url || "/";
  const path = original.split("?")[0];
  if (path === "/manifest.json" || path === "/manifest-4.3.0.json") {
    const r = await fetch(`http://127.0.0.1:${UPSTREAM_PORT}/manifest.json`);
    const manifest = await r.json();
    manifest.version = VERSION;
    manifest.catalogs = [
      { type: "channel", id: "sports-epg", name: "📺 SPORTS EPG • ALL GAMES & NETWORKS" },
      { type: "channel", id: "sports-guide", name: "🗓️ SPORTS GUIDE • NOW & NEXT" }
    ];
    manifest.liveTv = {
      ...(manifest.liveTv || {}),
      enabled: true,
      name: "XSportsX Sports Live TV",
      playlist: "/live-tv.m3u",
      epg: "/epg.xml",
      refreshSeconds: 60,
      guide: "/catalog/channel/sports-guide.json"
    };
    return send(res, 200, "application/json; charset=utf-8", JSON.stringify(manifest));
  }
  if (path === "/catalog/channel/sports-guide.json") return send(res, 200, "application/json; charset=utf-8", JSON.stringify(await guideCatalog()));
  if (path === "/epg") return send(res, 200, "application/json; charset=utf-8", JSON.stringify({ version: VERSION, type: "xmltv", playlist: `${BASE}/live-tv.m3u`, epg: `${BASE}/epg.xml`, guide: `${BASE}/catalog/channel/sports-guide.json`, refreshSeconds: 60 }));

  const upstream = await fetch(`http://127.0.0.1:${UPSTREAM_PORT}${original}`, {
    method: req.method,
    headers: { ...req.headers, host: `127.0.0.1:${UPSTREAM_PORT}` },
    body: req.method === "GET" || req.method === "HEAD" ? undefined : req
  });
  const type = upstream.headers.get("content-type") || "application/octet-stream";
  const body = Buffer.from(await upstream.arrayBuffer());
  res.writeHead(upstream.status, {
    "content-type": type,
    "cache-control": "no-store",
    "access-control-allow-origin": "*",
    "x-xsportsx-version": VERSION,
    "x-xsportsx-addon-id": "com.xsportsx.sports.epg"
  });
  res.end(body);
}

http.createServer((req, res) => proxy(req, res).catch(error => send(res, 502, "application/json; charset=utf-8", JSON.stringify({ error: "guide gateway unavailable", detail: String(error?.message || error) })))).listen(PORT, "0.0.0.0", () => {
  console.log(`XSportsX Sports EPG ${VERSION} guide gateway listening on ${PORT}`);
});
