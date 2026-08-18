import http from "node:http";
import { spawn } from "node:child_process";
import { getUfcData, ufcSections, getUfcOfficialRankings, getUfcOfficialAthletes } from "./ufc-data.js";
import { buildFightIntelligence } from "./ufc-intelligence.js";

const PORT = Number(process.env.PORT || 7000);
const BACKEND_PORT = Number(process.env.XSPORTSX_BACKEND_PORT || 7001);
const BACKEND = `http://127.0.0.1:${BACKEND_PORT}`;
const UFC_CACHE_MS = Number(process.env.UFC_GATEWAY_CACHE_MS || 300000);
let catalogCache = { at: 0, value: [] };
let rankingsCache = { at: 0, value: [] };
let athletesCache = { at: 0, value: [] };

const child = spawn(process.execPath, ["server-fixed.js"], { env: { ...process.env, PORT: String(BACKEND_PORT) }, stdio: "inherit" });
child.on("exit", code => { if (code && code !== 0) process.exitCode = code; });
async function backendJson(path) { const response = await fetch(`${BACKEND}${path}`); if (!response.ok) throw new Error(`Backend ${response.status}`); return response.json(); }
function clean(value) { return String(value || "").replace(/\s+/g, " ").trim(); }
function norm(value) { return clean(value).toLowerCase().replace(/[^a-z0-9]+/g, " ").trim(); }
function slug(value) { return norm(value).replace(/\s+/g, "-"); }
function findBackendEvent(detail, metas) { const target = norm(detail?.name); if (!target) return null; return metas.find(m => { const title = norm(m?.name); return title === target || title.includes(target) || target.includes(title); }) || null; }
function fightId(eventId, index) { return `sport:ufc-fight-${eventId}--${index}`; }
function parseFightId(id) { const raw = String(id || "").replace(/^sport:/, ""); const marker = "ufc-fight-"; if (!raw.startsWith(marker)) return null; const value = raw.slice(marker.length); const split = value.lastIndexOf("--"); return split > 0 ? { eventId: value.slice(0, split), index: Number(value.slice(split + 2)) } : null; }

async function ufcCatalog() {
  if (Date.now() - catalogCache.at < UFC_CACHE_MS) return catalogCache.value;
  const [data, backend] = await Promise.all([getUfcData(), backendJson("/catalog/sport/ufc.json").catch(() => ({ metas: [] }))]);
  const metas = Array.isArray(backend.metas) ? backend.metas : [];
  if (!data.length) { catalogCache = { at: Date.now(), value: metas }; return metas; }
  const out = [];
  for (const detail of data) {
    const source = findBackendEvent(detail, metas), sections = ufcSections(detail), fights = detail.fights || [];
    const enrichedFights = await Promise.all(fights.map(f => buildFightIntelligence(f)));
    const main = sections.mainCard || [];
    const mainEvent = enrichedFights.find(f => f.mainEvent) || enrichedFights[0];
    const coMain = enrichedFights.find(f => f.coMain) || enrichedFights[1];
    const videos = enrichedFights.map((fight, index) => {
      const label = fight.mainEvent ? "🔥 MAIN EVENT" : fight.coMain ? "⚡ CO-MAIN EVENT" : fight.title ? "🏆 TITLE FIGHT" : fight.bout || "FIGHT";
      const a = fight.fighter1?.name || "Fighter 1", b = fight.fighter2?.name || "Fighter 2";
      const c = fight.comparison || {};
      return { id: fightId(detail.id, index), title: `${label} • ${a} vs ${b}`, released: detail.date, thumbnail: fight.fighter1?.image || fight.fighter2?.image || detail.image || source?.poster, overview: `${fight.rounds || 3} ROUNDS • ${fight.bout || "UFC"}${fight.fighter1?.record || fight.fighter2?.record ? ` • ${fight.fighter1?.record || ""} vs ${fight.fighter2?.record || ""}` : ""}${fight.result ? ` • ${fight.result}` : ""}`, faceOff: { left: fight.fighter1, right: fight.fighter2, records: c.records || [], ranks: c.ranks || [], weightClass: c.weightClass || fight.bout || "UFC", titleFight: Boolean(c.titleFight), rounds: Number(c.rounds || fight.rounds || 3), watchLabel: "▶ WATCH FIGHT" } };
    });
    if (!videos.length && source) videos.push(...(source.videos || []));
    out.push({ id: `sport:ufc-event-${detail.id}`, type: "sport", name: `🥊 ${detail.name}`, poster: detail.image || source?.poster, background: detail.image || source?.background, description: `🥊 UFC FIGHT NIGHT • ${detail.date || ""}${detail.venue ? ` • ${detail.venue}` : ""}${detail.city ? ` • ${detail.city}` : ""}\n\n🔥 MAIN EVENT: ${mainEvent?.fighter1?.name || "TBA"} vs ${mainEvent?.fighter2?.name || "TBA"}\n⚡ CO-MAIN: ${coMain?.fighter1?.name || "TBA"} vs ${coMain?.fighter2?.name || "TBA"}\n\n🔥 MAIN CARD: ${main.length} • PRELIMS: ${sections.prelims.length}\n\n🔗 Official UFC event: ${detail.officialUrl}`, genres: ["Sports", "UFC", "MMA", "Fight Night"], releaseInfo: detail.date ? new Date(detail.date).toLocaleString() : "", videos, behaviorHints: { defaultVideoId: videos[0]?.id } });
  }
  catalogCache = { at: Date.now(), value: out }; return out;
}

async function ufcHomeCatalog() {
  const events = await ufcCatalog();
  const next = events[0];
  if (!next) return [];
  const videos = [
    { id: next.id, title: `🔥 NEXT EVENT • ${next.name.replace(/^🥊\s*/, "")}`, overview: next.description, thumbnail: next.poster },
    ...(next.videos || []).slice(0, 8),
    { id: "sport:ufc-rankings", title: "🏆 UFC RANKINGS", overview: "Official UFC rankings and Meta UFC rankings", thumbnail: "https://www.ufc.com/themes/custom/ufc/assets/img/ufc-logo.svg" },
    { id: "sport:ufc-fighters", title: "👊 UFC FIGHTERS", overview: "Official UFC athlete profiles", thumbnail: "https://www.ufc.com/themes/custom/ufc/assets/img/ufc-logo.svg" }
  ];
  return [{ id: "sport:ufc-home", type: "sport", name: "🥊 UFC • FIGHT NIGHT COMMAND CENTER", poster: next.poster, background: next.background, description: `🔥 NEXT EVENT\n${next.name}\n\n${next.description}\n\n▶ WATCH • 🏆 RANKINGS • 👊 FIGHTERS`, genres: ["Sports", "UFC", "MMA", "Fight Night", "Command Center"], videos, behaviorHints: { defaultVideoId: next.id } }];
}

async function ufcRankingsCatalog() {
  if (Date.now() - rankingsCache.at < UFC_CACHE_MS) return rankingsCache.value;
  const rows = await getUfcOfficialRankings();
  const metas = rows.slice(0, 150).map((fighter, index) => ({ id: `sport:ufc-ranking-${index}-${slug(fighter.name)}`, type: "sport", name: `🏆 ${fighter.rank ? `#${fighter.rank} ` : ""}${fighter.name}`, poster: fighter.image || "https://www.ufc.com/themes/custom/ufc/assets/img/ufc-logo.svg", background: fighter.image || "https://www.ufc.com/themes/custom/ufc/assets/img/ufc-logo.svg", description: `Official UFC Rankings • ${fighter.division || "Rankings"}\n\nOpen the official UFC profile for current stats and details.`, genres: ["Sports", "UFC", "Rankings"], videos: [{ id: `sport:ufc-ranking-${index}-${slug(fighter.name)}`, title: `🏆 ${fighter.name}`, overview: `Official UFC fighter profile: ${fighter.profileUrl}`, thumbnail: fighter.image }], behaviorHints: {} }));
  rankingsCache = { at: Date.now(), value: metas }; return metas;
}
async function ufcFightersCatalog() {
  if (Date.now() - athletesCache.at < UFC_CACHE_MS) return athletesCache.value;
  const rows = await getUfcOfficialAthletes();
  const metas = rows.slice(0, 150).map((fighter, index) => ({ id: `sport:ufc-fighter-${index}-${slug(fighter.name)}`, type: "sport", name: `👊 ${fighter.name}`, poster: fighter.image || "https://www.ufc.com/themes/custom/ufc/assets/img/ufc-logo.svg", background: fighter.image || "https://www.ufc.com/themes/custom/ufc/assets/img/ufc-logo.svg", description: `Official UFC athlete profile\n\n${fighter.profileUrl}`, genres: ["Sports", "UFC", "Fighters"], videos: [{ id: `sport:ufc-fighter-${index}-${slug(fighter.name)}`, title: `👊 ${fighter.name}`, overview: `Official UFC athlete profile: ${fighter.profileUrl}`, thumbnail: fighter.image }], behaviorHints: {} }));
  athletesCache = { at: Date.now(), value: metas }; return metas;
}

async function handleUfc(req, res) {
  const url = new URL(req.url, `http://${req.headers.host}`);
  if (url.pathname === "/catalog/sport/ufc-home.json") return json(res, { metas: await ufcHomeCatalog() });
  if (url.pathname === "/catalog/sport/ufc.json") return json(res, { metas: await ufcCatalog() });
  if (url.pathname === "/catalog/sport/ufc-rankings.json") return json(res, { metas: await ufcRankingsCatalog() });
  if (url.pathname === "/catalog/sport/ufc-fighters.json") return json(res, { metas: await ufcFightersCatalog() });
  if (url.pathname.startsWith("/meta/sport/ufc-home")) { const meta = (await ufcHomeCatalog())[0]; return meta ? json(res, { meta }) : json(res, { meta: null }, 404); }
  if (url.pathname.startsWith("/meta/sport/ufc-event-")) { const id = decodeURIComponent(url.pathname.split("/meta/sport/")[1].replace(/\.json$/, "")); const meta = (await ufcCatalog()).find(x => x.id === id); return meta ? json(res, { meta }) : json(res, { meta: null }, 404); }
  if (url.pathname.startsWith("/meta/sport/ufc-fight-")) { const id = decodeURIComponent(url.pathname.split("/meta/sport/")[1].replace(/\.json$/, "")); const parsed = parseFightId(id); const event = parsed ? (await ufcCatalog()).find(x => x.id === `sport:ufc-event-${parsed.eventId}`) : null; const video = parsed && event?.videos?.[parsed.index]; return video ? json(res, { meta: { id, type: "sport", name: video.title, poster: video.thumbnail, background: event.background, description: video.overview, genres: ["Sports", "UFC", "Fight"], videos: [video], faceOff: video.faceOff, behaviorHints: { defaultVideoId: video.id } } }) : json(res, { meta: null }, 404); }
  if (url.pathname.startsWith("/stream/sport/ufc-fight-")) { const id = decodeURIComponent(url.pathname.split("/stream/sport/")[1].replace(/\.json$/, "")); const parsed = parseFightId(id); if (!parsed) return json(res, { streams: [] }, 404); const event = (await ufcCatalog()).find(x => x.id === `sport:ufc-event-${parsed.eventId}`); const streams = event?.id ? await backendJson(`/stream/sport/${encodeURIComponent(event.id.replace(/^sport:/, ""))}.json`).catch(() => ({ streams: [] })) : { streams: [] }; return json(res, { streams: Array.isArray(streams.streams) ? streams.streams : [] }); }
  if (url.pathname.startsWith("/stream/sport/ufc-event-")) {
    const id = decodeURIComponent(url.pathname.split("/stream/sport/")[1].replace(/\.json$/, ""));
    const meta = (await ufcCatalog()).find(x => x.id === id); if (!meta) return json(res, { streams: [] }, 404);
    const backendId = meta.videos?.[0]?.id; const streams = backendId ? await backendJson(`/stream/sport/${encodeURIComponent(backendId.replace(/^sport:/, ""))}.json`).catch(() => ({ streams: [] })) : { streams: [] };
    const result = Array.isArray(streams.streams) ? [...streams.streams] : [];
    const enriched = await getUfcData(); const officialUrl = enriched.find(x => `sport:ufc-event-${x.id}` === id)?.officialUrl;
    if (officialUrl) result.push({ name: "🔗 Official UFC Event", externalUrl: officialUrl, title: "Official UFC event / watch information" });
    return json(res, { streams: result });
  }
  if (url.pathname.startsWith("/stream/sport/ufc-ranking-") || url.pathname.startsWith("/stream/sport/ufc-fighter-")) {
    const id = decodeURIComponent(url.pathname.split("/stream/sport/")[1].replace(/\.json$/, ""));
    const rows = id.startsWith("sport:ufc-ranking-") ? await ufcRankingsCatalog() : await ufcFightersCatalog();
    const meta = rows.find(x => x.id === id); const profile = meta?.videos?.[0]?.overview?.replace(/^.*?: /, "");
    return json(res, { streams: profile ? [{ name: "🔗 Official UFC Profile", externalUrl: profile, title: "Open official UFC profile" }] : [] });
  }
  return null;
}
function json(res, body, status = 200) { const text = JSON.stringify(body); res.writeHead(status, { "content-type": "application/json; charset=utf-8", "cache-control": "public,max-age=30" }); res.end(text); }

const server = http.createServer(async (req, res) => {
  try {
    const isUfc = /\/(catalog|meta|stream)\/sport\/ufc(?:\.json|-home(?:\.json)?|-event-|-fight-|-rankings\.json|-fighters\.json|-ranking-|-fighter-)/.test(req.url || "");
    if (isUfc) { const handled = await handleUfc(req, res); if (handled !== null) return; }
    const response = await fetch(`${BACKEND}${req.url}`, { method: req.method, headers: { accept: req.headers.accept || "*/*" } });
    res.writeHead(response.status, Object.fromEntries(response.headers.entries())); res.end(Buffer.from(await response.arrayBuffer()));
  } catch (error) { res.writeHead(502, { "content-type": "application/json; charset=utf-8" }); res.end(JSON.stringify({ error: "XSportsX gateway unavailable", detail: clean(error.message) })); }
});
server.listen(PORT, () => console.log(`XSportsX gateway listening on ${PORT}; backend on ${BACKEND_PORT}`));
process.on("SIGTERM", () => { child.kill("SIGTERM"); server.close(() => process.exit(0)); });
process.on("SIGINT", () => { child.kill("SIGINT"); server.close(() => process.exit(0)); });
