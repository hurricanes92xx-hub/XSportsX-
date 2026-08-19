import http from "node:http";
import { spawn } from "node:child_process";

const PORT = Number(process.env.PORT || 7000);
const INTERNAL = Number(process.env.XSPORTSX_PUBLIC_INTERNAL_PORT || 7005);
const BASE = process.env.BASE_URL || "https://xsportsx.onrender.com";
const VERSION = "4.1.0";
const POSTER = "https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png";

const manifest = {
  id: "com.xsportsx.sports.epg",
  version: VERSION,
  name: "XSportsX Sports EPG",
  description: "Unified sports EPG with live and upcoming games, broadcast networks, UFC, NCAA Football and conference network coverage.",
  logo: POSTER,
  background: POSTER,
  resources: [
    { name: "catalog", types: ["channel"] },
    { name: "meta", types: ["channel"], idPrefixes: ["sport:"] },
    { name: "stream", types: ["channel"], idPrefixes: ["sport:"] }
  ],
  types: ["channel"],
  idPrefixes: ["sport:"],
  catalogs: [{ type: "channel", id: "sports-epg", name: "📺 SPORTS EPG • ALL GAMES & NETWORKS" }],
  behaviorHints: { configurable: false, configurationRequired: false }
};

function send(res, status, value) {
  const body = JSON.stringify(value);
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store, max-age=0, must-revalidate",
    "pragma": "no-cache",
    "expires": "0",
    "access-control-allow-origin": "*"
  });
  res.end(body);
}

function rewritePayload(payload) {
  if (!payload || typeof payload !== "object") return payload;
  const fix = (m) => m && typeof m === "object"
    ? { ...m, type: "channel", posterShape: m.posterShape || "landscape" }
    : m;
  if (Array.isArray(payload.metas)) payload.metas = payload.metas.map(fix);
  if (payload.meta) payload.meta = fix(payload.meta);
  return payload;
}

const child = spawn(process.execPath, ["render-entry.js"], {
  env: { ...process.env, PORT: String(INTERNAL), BASE_URL: BASE },
  stdio: "inherit"
});
child.on("exit", code => { if (code && code !== 0) process.exitCode = code; });

async function proxy(req, res) {
  const original = req.url || "/";
  const path = original.split("?")[0];

  if (path === "/manifest.json" || path === "/manifest-4.1.0.json") return send(res, 200, manifest);
  if (path === "/health") return send(res, 200, { ok: true, version: VERSION, addonId: manifest.id, type: "channel" });

  const translated = original
    .replace(/^\/catalog\/channel\//, "/catalog/sport/")
    .replace(/^\/meta\/channel\//, "/meta/sport/")
    .replace(/^\/stream\/channel\//, "/stream/sport/");

  try {
    const upstream = await fetch(`http://127.0.0.1:${INTERNAL}${translated}`, {
      method: req.method,
      headers: { ...req.headers, host: `127.0.0.1:${INTERNAL}` },
      body: req.method === "GET" || req.method === "HEAD" ? undefined : req
    });
    const contentType = upstream.headers.get("content-type") || "application/json";
    const buf = Buffer.from(await upstream.arrayBuffer());
    if (contentType.includes("application/json")) {
      try { return send(res, upstream.status, rewritePayload(JSON.parse(buf.toString("utf8")))); }
      catch {}
    }
    res.writeHead(upstream.status, { "content-type": contentType, "cache-control": "no-store", "access-control-allow-origin": "*" });
    res.end(buf);
  } catch (err) {
    send(res, 502, { error: "upstream unavailable", detail: String(err?.message || err) });
  }
}

http.createServer(proxy).listen(PORT, "0.0.0.0", () => {
  console.log(`XSportsX Sports EPG ${VERSION} (${manifest.id}) listening on ${PORT}`);
});
