import http from "node:http";
import { spawn } from "node:child_process";

const PUBLIC_PORT = Number(process.env.PORT || 7000);
const INTERNAL_PORT = Number(process.env.XSPORTSX_COMMAND_CENTER_PORT || 7003);
const BASE = process.env.BASE_URL || "https://xsportsx.onrender.com";
const PREFIX = process.env.XSPORTSX_PREFIX || "/v443";
const XTREAM_URL = String(process.env.XTREAM_URL || process.env.XTREAM_SERVER_URL || "").trim().replace(/\/+$/, "");
const XTREAM_USER = String(process.env.XTREAM_USERNAME || "").trim();
const XTREAM_PASS = String(process.env.XTREAM_PASSWORD || "").trim();
const XTREAM_ENABLED = Boolean(XTREAM_URL && XTREAM_USER && XTREAM_PASS);
const CACHE_MS = Number(process.env.XTREAM_CACHE_MS || 60000);
let streamCache = { at: 0, rows: [] };

const child = spawn(process.execPath, ["command-center.js"], {
  env: { ...process.env, PORT: String(INTERNAL_PORT), BASE_URL: BASE },
  stdio: "inherit",
});
child.on("exit", code => { if (code && code !== 0) process.exitCode = code; });

function json(res, body, status = 200) {
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store, no-cache, max-age=0, must-revalidate",
    "access-control-allow-origin": "*",
  });
  res.end(JSON.stringify(body));
}

async function getJson(url) {
  const r = await fetch(url, { headers: { accept: "application/json" } });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

function normalize(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\b(vs|versus|at)\b/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function tokens(value) {
  const stop = new Set(["the", "and", "game", "live", "tv", "channel", "sports", "network", "hd", "fhd", "uhd", "4k", "east", "west", "main", "event"]);
  return normalize(value).split(" ").filter(x => x.length >= 3 && !stop.has(x));
}

function scoreChannel(eventName, channel) {
  const wanted = tokens(eventName);
  const hay = normalize(`${channel.name || ""} ${channel.category_name || ""}`);
  if (!wanted.length || !hay) return 0;
  const hits = wanted.filter(t => hay.includes(t));
  const unique = [...new Set(hits)];
  let score = unique.length * 20;
  if (unique.length >= 2) score += 45;
  if (channel.name && wanted.some(t => normalize(channel.name).includes(t))) score += 10;
  if (/espn|nfl network|nba tv|nhl network|mlb network|sec network|acc network|big ten network|fox sports|tnt|tbs/.test(hay)) score += 5;
  if (/\b(4k|uhd|fhd|hd)\b/.test(hay)) score += 2;
  return score;
}

async function xtreamLiveStreams() {
  if (!XTREAM_ENABLED) return [];
  const now = Date.now();
  if (now - streamCache.at < CACHE_MS) return streamCache.rows;
  const api = `${XTREAM_URL}/player_api.php?username=${encodeURIComponent(XTREAM_USER)}&password=${encodeURIComponent(XTREAM_PASS)}&action=get_live_streams`;
  try {
    const rows = await getJson(api);
    streamCache = { at: now, rows: Array.isArray(rows) ? rows : [] };
  } catch {
    streamCache = { at: now, rows: [] };
  }
  return streamCache.rows;
}

function xtreamStream(channel) {
  const ext = String(channel.container_extension || "ts").replace(/[^a-z0-9]/gi, "") || "ts";
  return {
    name: `📺 Xtream • ${channel.name || "Live channel"}`,
    title: channel.name || "Xtream live channel",
    url: `${XTREAM_URL}/live/${encodeURIComponent(XTREAM_USER)}/${encodeURIComponent(XTREAM_PASS)}/${encodeURIComponent(channel.stream_id)}.${ext}`,
    behaviorHints: { bingeGroup: "xsportsx-xtream" },
  };
}

async function augmentStream(req, res, path) {
  const match = path.match(/^\/stream\/channel\/(.+?)\.json$/);
  if (!match || !XTREAM_ENABLED) return proxy(req, res, `${PREFIX}${path}`);
  const id = decodeURIComponent(match[1]);
  try {
    const meta = await getJson(`http://127.0.0.1:${INTERNAL_PORT}${PREFIX}/meta/channel/${encodeURIComponent(id)}.json`);
    const eventName = meta?.meta?.name || "";
    const base = await getJson(`http://127.0.0.1:${INTERNAL_PORT}${PREFIX}${path}`);
    const streams = Array.isArray(base?.streams) ? [...base.streams] : [];
    const channels = await xtreamLiveStreams();
    const ranked = channels
      .map(c => ({ c, score: scoreChannel(eventName, c) }))
      .filter(x => x.score >= 65 && x.c?.stream_id != null)
      .sort((a, b) => b.score - a.score)
      .slice(0, 5);
    for (const { c } of ranked) streams.push(xtreamStream(c));
    return json(res, { streams });
  } catch {
    return proxy(req, res, `${PREFIX}${path}`);
  }
}

async function proxy(req, res, path) {
  const r = await fetch(`http://127.0.0.1:${INTERNAL_PORT}${path}`, {
    method: req.method,
    headers: { accept: req.headers.accept || "*/*" },
  });
  const headers = {
    "content-type": r.headers.get("content-type") || "application/octet-stream",
    "cache-control": "no-store",
    "access-control-allow-origin": "*",
  };
  res.writeHead(r.status, headers);
  res.end(Buffer.from(await r.arrayBuffer()));
}

const server = http.createServer(async (req, res) => {
  try {
    const u = new URL(req.url || "/", `http://${req.headers.host}`);
    const versioned = u.pathname.startsWith(PREFIX + "/");
    const path = versioned ? u.pathname.slice(PREFIX.length) || "/" : u.pathname;
    if (path === "/health") return json(res, { ok: true, xtreamConfigured: XTREAM_ENABLED, version: "4.4.3" });
    if (path.startsWith("/stream/channel/")) return augmentStream(req, res, path);
    return proxy(req, res, `${PREFIX}${path}${u.search || ""}`);
  } catch (e) {
    return json(res, { error: "XSportsX front gateway unavailable", detail: String(e?.message || e) }, 502);
  }
});

server.listen(PUBLIC_PORT, "0.0.0.0", () => {
  console.log(`XSportsX Render front listening on ${PUBLIC_PORT}; Xtream configured: ${XTREAM_ENABLED}`);
});
