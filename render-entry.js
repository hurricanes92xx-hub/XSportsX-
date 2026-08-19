import http from "node:http";
import { spawn } from "node:child_process";

const PUBLIC_PORT = Number(process.env.PORT || 7000);
const GATEWAY_PORT = Number(process.env.XSPORTSX_GATEWAY_PORT || 7002);
const BACKEND_PORT = Number(process.env.XSPORTSX_BACKEND_PORT || 7001);
const BASE = process.env.BASE_URL || `https://xsportsx.onrender.com`;
const VERSION = "3.9.7";
const RAW = "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/main/";

const manifest = {
  id: "com.xsportsx.live",
  version: VERSION,
  name: "XSportsX",
  description: "XSportsX — cinematic, collection-first live sports hub for Nuvio.",
  logo: `${RAW}logo.svg`,
  background: `${RAW}background.svg`,
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
    { type: "sport", id: "ncaaf", name: "🏈 NCAA FOOTBALL" },
    { type: "sport", id: "cfp-watch", name: "🏆 NCAA FOOTBALL • CFP WATCH" }
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

async function proxy(req, res) {
  const target = `http://127.0.0.1:${GATEWAY_PORT}${req.url}`;
  try {
    const headers = { ...req.headers, host: `127.0.0.1:${GATEWAY_PORT}` };
    const upstream = await fetch(target, { method: req.method, headers, body: req.method === "GET" || req.method === "HEAD" ? undefined : req });
    res.writeHead(upstream.status, {
      "content-type": upstream.headers.get("content-type") || "application/json",
      "cache-control": upstream.headers.get("cache-control") || "no-store",
      "access-control-allow-origin": "*"
    });
    if (upstream.body) {
      for await (const chunk of upstream.body) res.write(Buffer.from(chunk));
    }
    res.end();
  } catch (error) {
    res.writeHead(502, { "content-type": "application/json", "access-control-allow-origin": "*" });
    res.end(JSON.stringify({ error: "gateway unavailable", detail: String(error?.message || error) }));
  }
}

const server = http.createServer(async (req, res) => {
  if (req.url === "/manifest.json") return sendJson(res, manifest);
  if (req.url === "/health") return sendJson(res, { ok: true, version: VERSION, gateway: GATEWAY_PORT, backend: BACKEND_PORT, baseUrl: BASE });
  return proxy(req, res);
});

server.listen(PUBLIC_PORT, "0.0.0.0", () => {
  console.log(`XSportsX Render entrypoint ${VERSION} listening on ${PUBLIC_PORT}; gateway ${GATEWAY_PORT}; backend ${BACKEND_PORT}`);
});
