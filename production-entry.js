import http from "node:http";
import { spawn } from "node:child_process";

const PORT = Number(process.env.PORT || 7000);
const UPSTREAM_PORT = Number(process.env.XSPORTSX_PRODUCTION_UPSTREAM_PORT || 7010);
const BASE = process.env.BASE_URL || "https://xsportsx.onrender.com";
const VERSION = "4.3.2";
const ADDON_ID = "com.xsportsx.sports.epg";

const child = spawn(process.execPath, ["render-entry.js"], {
  env: { ...process.env, PORT: String(UPSTREAM_PORT), BASE_URL: BASE },
  stdio: "inherit"
});
child.on("exit", code => { if (code && code !== 0) process.exitCode = code; });

function headers(type = "application/json; charset=utf-8") {
  return { "content-type": type, "cache-control": "no-store, no-cache, max-age=0, must-revalidate", "pragma": "no-cache", "expires": "0", "access-control-allow-origin": "*", "x-xsportsx-version": VERSION, "x-xsportsx-addon-id": ADDON_ID };
}
function send(res, status, body, type = "application/json; charset=utf-8") { res.writeHead(status, headers(type)); res.end(body); }

async function proxy(req, res) {
  const original = req.url || "/", path = original.split("?")[0];
  if (path === "/manifest.json" || path === "/manifest-4.3.2.json") {
    const upstream = await fetch(`http://127.0.0.1:${UPSTREAM_PORT}/manifest.json`);
    const manifest = await upstream.json();
    manifest.id = ADDON_ID;
    manifest.version = VERSION;
    manifest.name = "XSportsX Sports EPG";
    manifest.catalogs = [
      { type: "channel", id: "sports-epg", name: "📺 SPORTS EPG • ALL GAMES & NETWORKS" }
    ];
    manifest.liveTv = {
      ...(manifest.liveTv || {}),
      enabled: true,
      name: "XSportsX Sports Live TV",
      playlist: `${BASE}/live-tv.m3u`,
      epg: `${BASE}/epg.xml`,
      refreshSeconds: 60,
      guide: `${BASE}/catalog/channel/sports-epg.json`
    };
    return send(res, 200, JSON.stringify(manifest));
  }
  if (path === "/health") return send(res, 200, JSON.stringify({ ok: true, version: VERSION, addonId: ADDON_ID, type: "channel", liveTv: true, epg: true }));
  if (path === "/live-tv.json") return send(res, 200, JSON.stringify({ id: ADDON_ID, version: VERSION, name: "XSportsX Sports Live TV", playlist: `${BASE}/live-tv.m3u`, epg: `${BASE}/epg.xml`, refreshSeconds: 60, catalog: `${BASE}/catalog/channel/sports-epg.json` }));
  if (path === "/nuvio.m3u") {
    const upstream = await fetch(`http://127.0.0.1:${UPSTREAM_PORT}/live-tv.m3u`);
    return send(res, upstream.status, await upstream.text(), "application/x-mpegURL; charset=utf-8");
  }
  if (path === "/nuvio-epg.xml") {
    const upstream = await fetch(`http://127.0.0.1:${UPSTREAM_PORT}/epg.xml`);
    return send(res, upstream.status, await upstream.text(), "application/xml; charset=utf-8");
  }
  const upstream = await fetch(`http://127.0.0.1:${UPSTREAM_PORT}${original}`, { method: req.method, headers: { ...req.headers, host: `127.0.0.1:${UPSTREAM_PORT}` }, body: req.method === "GET" || req.method === "HEAD" ? undefined : req });
  const type = upstream.headers.get("content-type") || "application/octet-stream", body = Buffer.from(await upstream.arrayBuffer());
  res.writeHead(upstream.status, headers(type)); res.end(body);
}

http.createServer((req, res) => proxy(req, res).catch(error => send(res, 502, JSON.stringify({ error: "production gateway unavailable", detail: String(error?.message || error) })))).listen(PORT, "0.0.0.0", () => console.log(`XSportsX Sports EPG ${VERSION} production gateway listening on ${PORT}`));
