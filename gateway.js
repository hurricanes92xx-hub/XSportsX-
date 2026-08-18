import http from "node:http";
import { spawn } from "node:child_process";
import { getUfcData, ufcSections } from "./ufc-data.js";

const PORT = Number(process.env.PORT || 7000);
const BACKEND_PORT = Number(process.env.XSPORTSX_BACKEND_PORT || 7001);
const BACKEND = `http://127.0.0.1:${BACKEND_PORT}`;
const UFC_CACHE_MS = Number(process.env.UFC_GATEWAY_CACHE_MS || 300000);
let backendReady = false;
let catalogCache = { at: 0, value: [] };

const child = spawn(process.execPath, ["server-fixed.js"], {
  env: { ...process.env, PORT: String(BACKEND_PORT) },
  stdio: "inherit"
});
child.on("exit", code => {
  if (code && code !== 0) process.exitCode = code;
});

async function backendJson(path) {
  const response = await fetch(`${BACKEND}${path}`);
  if (!response.ok) throw new Error(`Backend ${response.status}`);
  return response.json();
}

function clean(value) { return String(value || "").replace(/\s+/g, " ").trim(); }
function norm(value) { return clean(value).toLowerCase().replace(/[^a-z0-9]+/g, " ").trim(); }
function findBackendEvent(detail, metas) {
  const target = norm(detail?.name);
  if (!target) return null;
  return metas.find(m => {
    const title = norm(m?.name);
    return title === target || title.includes(target) || target.includes(title);
  }) || null;
}

async function ufcCatalog() {
  if (Date.now() - catalogCache.at < UFC_CACHE_MS) return catalogCache.value;
  const [data, backend] = await Promise.all([getUfcData(), backendJson("/catalog/sport/ufc.json").catch(() => ({ metas: [] }))]);
  const metas = Array.isArray(backend.metas) ? backend.metas : [];
  const out = [];
  for (const detail of data) {
    const source = findBackendEvent(detail, metas);
    const sections = ufcSections(detail);
    const fights = detail.fights || [];
    const videos = fights.map((fight, index) => {
      const label = fight.mainEvent ? "🔥 MAIN EVENT" : fight.coMain ? "⚡ CO-MAIN EVENT" : fight.title ? "🏆 TITLE FIGHT" : fight.bout || "FIGHT";
      const a = fight.fighter1?.name || "Fighter 1";
      const b = fight.fighter2?.name || "Fighter 2";
      return {
        id: source?.id || `sport:ufc-fight-${detail.id}-${index}`,
        title: `${label} • ${a} vs ${b}`,
        released: detail.date,
        thumbnail: detail.image || source?.poster,
        overview: `${fight.rounds || 3} ROUNDS • ${fight.bout || "UFC"}${fight.result ? ` • ${fight.result}` : ""}`
      };
    });
    if (!videos.length && source) videos.push(...(source.videos || []));
    out.push({
      id: `sport:ufc-event-${detail.id}`,
      type: "sport",
      name: `🥊 ${detail.name}`,
      poster: detail.image || source?.poster,
      background: detail.image || source?.background,
      description: `🥊 UFC FIGHT NIGHT • ${detail.date || ""}${detail.venue ? ` • ${detail.venue}` : ""}${detail.city ? ` • ${detail.city}` : ""}\\n\\n🔥 MAIN EVENT: ${sections.mainCard[0]?.fighter1?.name || "TBA"} vs ${sections.mainCard[0]?.fighter2?.name || "TBA"}\\n\\nMAIN CARD: ${sections.mainCard.length} • PRELIMS: ${sections.prelims.length}\\n\\nOfficial UFC event information: ${detail.officialUrl}`,
      genres: ["Sports", "UFC", "MMA", "Fight Night"],
      releaseInfo: detail.date ? new Date(detail.date).toLocaleString() : "",
      videos,
      behaviorHints: { defaultVideoId: videos[0]?.id }
    });
  }
  catalogCache = { at: Date.now(), value: out };
  return out;
}

async function handleUfc(req, res) {
  const url = new URL(req.url, `http://${req.headers.host}`);
  if (url.pathname === "/catalog/sport/ufc.json") {
    return json(res, { metas: await ufcCatalog() });
  }
  if (url.pathname.startsWith("/meta/sport/ufc-event-")) {
    const id = decodeURIComponent(url.pathname.split("/meta/sport/")[1].replace(/\.json$/, ""));
    const meta = (await ufcCatalog()).find(x => x.id === id);
    return meta ? json(res, { meta }) : json(res, { meta: null }, 404);
  }
  if (url.pathname.startsWith("/stream/sport/ufc-event-")) {
    const id = decodeURIComponent(url.pathname.split("/stream/sport/")[1].replace(/\.json$/, ""));
    const meta = (await ufcCatalog()).find(x => x.id === id);
    if (!meta) return json(res, { streams: [] }, 404);
    const sourceVideo = meta.videos?.[0];
    const streams = sourceVideo?.id ? await backendJson(`/stream/sport/${encodeURIComponent(sourceVideo.id.replace(/^sport:/, ""))}.json`).catch(() => ({ streams: [] })) : { streams: [] };
    const result = Array.isArray(streams.streams) ? [...streams.streams] : [];
    const officialUrl = (await getUfcData()).find(x => `sport:ufc-event-${x.id}` === id)?.officialUrl;
    if (officialUrl) result.push({ name: "🔗 Official UFC Event", externalUrl: officialUrl, title: "Official UFC event / watch information" });
    return json(res, { streams: result });
  }
  return null;
}

function json(res, body, status = 200) {
  const text = JSON.stringify(body);
  res.writeHead(status, { "content-type": "application/json; charset=utf-8", "cache-control": "public,max-age=30" });
  res.end(text);
}

const server = http.createServer(async (req, res) => {
  try {
    const isUfc = /\/(catalog|meta|stream)\/sport\/ufc(?:\.json|-event-)/.test(req.url || "");
    if (isUfc) {
      const handled = await handleUfc(req, res);
      if (handled !== null) return;
    }
    const response = await fetch(`${BACKEND}${req.url}`, { method: req.method, headers: { accept: req.headers.accept || "*/*" } });
    res.writeHead(response.status, Object.fromEntries(response.headers.entries()));
    res.end(Buffer.from(await response.arrayBuffer()));
  } catch (error) {
    res.writeHead(502, { "content-type": "application/json; charset=utf-8" });
    res.end(JSON.stringify({ error: "XSportsX gateway unavailable", detail: clean(error.message) }));
  }
});

server.listen(PORT, () => console.log(`XSportsX gateway listening on ${PORT}; backend on ${BACKEND_PORT}`));

process.on("SIGTERM", () => { child.kill("SIGTERM"); server.close(() => process.exit(0)); });
process.on("SIGINT", () => { child.kill("SIGINT"); server.close(() => process.exit(0)); });
