import express from "express";
import { getEvents, streamsFor, providerStatus } from "./providers.js";
import { TTLCache } from "./core.js";
import fs from "node:fs";
import path from "node:path";

const app = express();
const PORT = Number(process.env.PORT || 7000);
const BASE_URL = process.env.BASE_URL || `http://localhost:${PORT}`;
const cache = new TTLCache();
const eventCacheTtl = Number(process.env.EVENT_REFRESH_MS || 60000);
const CONFIGURED_TZ = process.env.DEFAULT_TIMEZONE || "UTC";

function poster(id) { return `${BASE_URL}/poster/${encodeURIComponent(id)}.svg`; }

function esc(x = "") {
  return String(x).replaceAll("&","&amp;").replaceAll("<","&lt;")
    .replaceAll(">","&gt;").replaceAll('"',"&quot;");
}

function meta(e) {
  return {
    id: e.id,
    type: "sport",
    name: e.title,
    poster: poster(e.eventId),
    background: poster(`${e.eventId}-bg`),
    description: `${e.state === "in" ? "● LIVE • " : ""}${e.detail || e.league}${e.venue ? ` • ${e.venue}` : ""}`,
    genres: ["Sports", e.sport, e.league].filter(Boolean),
    releaseInfo: e.start ? new Date(e.start).toLocaleString() : "",
    videos: [{
      id: e.id,
      title: e.title,
      released: e.start,
      thumbnail: poster(e.eventId)
    }],
    behaviorHints: { defaultVideoId: e.id }
  };
}

async function events() {
  const key = "events:7day";
  const cached = cache.get(key);
  if (cached) return cached;
  return cache.set(key, await getEvents({ days: 7 }), eventCacheTtl);
}

function filterCatalog(all, id) {
  const now = Date.now();
  if (id === "live-now") return all.filter(e => e.state === "in");
  if (id === "starting-soon") return all.filter(e => {
    const t = new Date(e.start || 0).getTime();
    return t > now && t <= now + 120 * 60_000;
  });
  if (id === "upcoming") return all.filter(e => new Date(e.start || 0).getTime() > now);
  if (id === "favorites") return all; // Favorites are client-side unless configured.
  if (id === "today") return all.filter(e => {
    const fmt = new Intl.DateTimeFormat("en-US", { timeZone: CONFIGURED_TZ, year:"numeric", month:"2-digit", day:"2-digit" });
    return fmt.format(new Date(e.start || 0)) === fmt.format(new Date());
  });
  return all.filter(e => e.sport === id || String(e.league).toLowerCase() === id.toLowerCase());
}

app.use(express.static("public"));

app.get("/manifest.json", (_, res) => {
  const manifest = JSON.parse(fs.readFileSync(path.join(process.cwd(), "manifest.json"), "utf8"));
  manifest.logo = `${BASE_URL}/logo.svg`;
  manifest.background = `${BASE_URL}/background.svg`;
  res.json(manifest);
});

app.get("/catalog/sport/:catalog.json", async (req,res) => {
  try {
    const result = filterCatalog(await events(), req.params.catalog);
    res.json({ metas: result.map(meta) });
  } catch {
    res.status(502).json({ metas: [] });
  }
});

app.get("/meta/sport/:id.json", async (req,res) => {
  const id = req.params.id.replace(/^sport:/,"");
  const e = (await events()).find(x => x.eventId === id);
  if (!e) return res.status(404).json({ meta: null });
  res.json({ meta: meta(e) });
});

app.get("/stream/sport/:id.json", async (req,res) => {
  const id = req.params.id.replace(/^sport:/,"");
  const e = (await events()).find(x => x.eventId === id);
  if (!e) return res.json({ streams: [] });
  res.json({ streams: await streamsFor(e) });
});

app.get("/sources/status", (_,res) => {
  const p = providerStatus();
  res.json({
    ...p,
    security: {
      credentialsConfigured: Boolean(process.env.AUTHORIZED_XTREAM_SOURCES || process.env.AUTHORIZED_M3U_SOURCES),
      credentialsExposed: false
    }
  });
});

app.get("/health", (_,res) => res.json({
  ok: true,
  name: "XSportsX",
  version: "2.2.0",
  uptime: process.uptime(),
  cacheEntries: cache.size(),
  providers: providerStatus()
}));

app.get("/poster/:id.svg", async (req,res) => {
  const id = decodeURIComponent(req.params.id).replace(/-bg$/,"");
  const e = (await events()).find(x => x.eventId === id);
  const title = e ? `${e.away.short || e.away.name}  VS  ${e.home.short || e.home.name}` : "SPORTSX";
  const detail = e ? (e.state === "in" ? "● LIVE" : new Date(e.start).toLocaleTimeString([], {hour:"numeric", minute:"2-digit"})) : "LIVE SPORTS";
  res.type("image/svg+xml").send(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 450">
<defs><linearGradient id="g"><stop stop-color="#030914"/><stop offset=".58" stop-color="#12345f"/><stop offset="1" stop-color="#061125"/></linearGradient><radialGradient id="r"><stop stop-color="#ff7430" stop-opacity=".65"/><stop offset="1" stop-color="#ff7430" stop-opacity="0"/></radialGradient></defs>
<rect width="800" height="450" fill="url(#g)"/><circle cx="90" cy="50" r="240" fill="url(#r)"/><path d="M0 360 Q220 220 410 345 T800 260 V450 H0Z" fill="#02050b" opacity=".6"/>
<text x="38" y="55" fill="#9fb7d8" font-family="Arial" font-size="20" font-weight="700">SPORTSX</text>
${e?.state==="in" ? `<rect x="650" y="28" width="110" height="34" rx="17" fill="#e43d3d"/><text x="705" y="51" text-anchor="middle" fill="white" font-family="Arial" font-size="16" font-weight="700">● LIVE</text>` : ""}
${e?.away.logo ? `<image href="${esc(e.away.logo)}" x="135" y="100" width="170" height="170" preserveAspectRatio="xMidYMid meet"/>` : ""}
${e?.home.logo ? `<image href="${esc(e.home.logo)}" x="495" y="100" width="170" height="170" preserveAspectRatio="xMidYMid meet"/>` : ""}
<text x="400" y="320" text-anchor="middle" fill="white" font-family="Arial" font-size="28" font-weight="800">${esc(title)}</text>
<text x="400" y="355" text-anchor="middle" fill="#a8bdd8" font-family="Arial" font-size="21">${esc(detail)}</text></svg>`);
});

app.listen(PORT, () => console.log(`XSportsX ${BASE_URL}`));
