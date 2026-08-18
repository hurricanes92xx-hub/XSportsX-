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

// Home-screen presentation for Nuvio. These are intentionally collection cards,
// not event rows, so the sports area reads like the Studios / Networks sections
// in the reference design.
const LEAGUES = [
  ["nfl", "NFL", "NFL", "football"],
  ["nba", "NBA", "NBA", "basketball"],
  ["nhl", "NHL", "NHL", "hockey"],
  ["mlb", "MLB", "MLB", "baseball"],
  ["ncaaf", "NCAA Football", "NCAA FB", "football"],
  ["ncaab", "NCAA Basketball", "NCAA BB", "basketball"],
  ["wnba", "WNBA", "WNBA", "basketball"],
  ["mls", "MLS", "MLS", "soccer"],
  ["premier-league", "Premier League", "EPL", "soccer"],
  ["la-liga", "La Liga", "LALIGA", "soccer"],
  ["f1", "Formula 1", "F1", "racing"],
  ["motogp", "MotoGP", "MotoGP", "racing"],
  ["ufc", "UFC", "UFC", "mma"],
  ["boxing", "Boxing", "BOX", "boxing"],
  ["atp", "ATP Tennis", "ATP", "tennis"],
  ["wta", "WTA Tennis", "WTA", "tennis"],
  ["pga", "PGA Golf", "PGA", "golf"],
  ["rugby", "Rugby", "RUGBY", "rugby"],
  ["cricket", "Cricket", "CRICKET", "cricket"],
  ["pdc", "Darts", "PDC", "darts"],
  ["afl", "AFL", "AFL", "football"]
].map(([id, name, short, sport]) => ({ id, name, short, sport }));

const leagueMap = new Map(LEAGUES.map(x => [x.id, x]));

const FAVORITE_TEAMS = [
  { id: "miami-hurricanes-football", name: "Miami Hurricanes Football", short: "Miami Hurricanes", sport: "ncaaf", aliases: ["Miami Hurricanes", "Miami (FL) Hurricanes"] },
  { id: "miami-hurricanes-basketball", name: "Miami Hurricanes Basketball", short: "Miami Hurricanes", sport: "ncaab", aliases: ["Miami Hurricanes", "Miami (FL) Hurricanes"] },
  { id: "miami-dolphins", name: "Miami Dolphins", short: "Dolphins", sport: "nfl", aliases: ["Miami Dolphins"] },
  { id: "miami-heat", name: "Miami Heat", short: "Heat", sport: "nba", aliases: ["Miami Heat"] },
  { id: "tampa-bay-lightning", name: "Tampa Bay Lightning", short: "Lightning", sport: "nhl", aliases: ["Tampa Bay Lightning"] }
];

const favoriteTeamMap = new Map(FAVORITE_TEAMS.map(x => [x.id, x]));
function teamPoster(id) { return `${BASE_URL}/teams/${encodeURIComponent(id)}.gif`; }

function favoriteTeamMatches(teamConfig, all) {
  return all.filter(e => {
    if (e.sport !== teamConfig.sport) return false;
    const names = [e.home?.name, e.home?.short, e.away?.name, e.away?.short].filter(Boolean).map(x => String(x).toLowerCase());
    return teamConfig.aliases.some(alias => names.some(n => n === alias.toLowerCase() || n.includes(alias.toLowerCase())));
  });
}

function favoriteTeamMeta(teamConfig, all) {
  const matches = favoriteTeamMatches(teamConfig, all);
  const videos = matches.slice(0, 100).map(e => ({
    id: e.id,
    title: `${e.state === "in" ? "🔴 LIVE • " : ""}${e.title}`,
    released: e.start,
    thumbnail: poster(e.eventId),
    overview: `${e.detail || e.league}${e.venue ? ` • ${e.venue}` : ""}`
  }));
  const live = matches.filter(e => e.state === "in").length;
  return {
    id: `sport:team-${teamConfig.id}`,
    type: "sport",
    name: teamConfig.name,
    poster: teamPoster(teamConfig.id),
    background: teamPoster(teamConfig.id),
    description: `${live ? `${live} LIVE NOW • ` : ""}${matches.length} upcoming/recent event${matches.length === 1 ? "" : "s"}`,
    genres: ["Sports", "Favorite Teams", teamConfig.sport],
    videos,
    behaviorHints: { defaultVideoId: videos[0]?.id }
  };
}

function poster(id) { return `${BASE_URL}/poster/${encodeURIComponent(id)}.svg`; }
function leaguePoster(id) { return `${BASE_URL}/leagues/${encodeURIComponent(id)}.gif`; }

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

function leagueEventsMeta(league, all) {
  const matches = all.filter(e =>
    e.sport === league.id ||
    String(e.league || "").toLowerCase() === league.id.toLowerCase()
  );
  const videos = matches.slice(0, 100).map(e => ({
    id: e.id,
    title: `${e.state === "in" ? "🔴 LIVE • " : ""}${e.title}`,
    released: e.start,
    thumbnail: poster(e.eventId),
    overview: `${e.detail || e.league}${e.venue ? ` • ${e.venue}` : ""}`
  }));
  const live = matches.filter(e => e.state === "in").length;
  return {
    id: `sport:league-${league.id}`,
    type: "sport",
    name: league.name,
    poster: leaguePoster(league.id),
    background: leaguePoster(league.id),
    description: `${live ? `${live} LIVE NOW • ` : ""}${matches.length} scheduled event${matches.length === 1 ? "" : "s"}`,
    genres: ["Sports", league.sport, league.name].filter(Boolean),
    videos,
    behaviorHints: { defaultVideoId: videos[0]?.id }
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
  if (id === "favorites") return all;
  const favorite = favoriteTeamMap.get(id);
  if (favorite) return favoriteTeamMatches(favorite, all);
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

// A single Nuvio row of animated league cards. Each card opens a collection meta
// containing that league's events, instead of exposing dozens of event rows.
app.get("/catalog/sport/sports-leagues.json", async (_, res) => {
  try {
    const all = await events();
    res.json({ metas: LEAGUES.map(league => leagueEventsMeta(league, all)) });
  } catch {
    res.status(502).json({ metas: [] });
  }
});


app.get("/catalog/sport/favorite-teams.json", async (_, res) => {
  try {
    const all = await events();
    res.json({ metas: FAVORITE_TEAMS.map(team => favoriteTeamMeta(team, all)) });
  } catch {
    res.status(502).json({ metas: [] });
  }
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
  if (id.startsWith("league-")) {
    const league = leagueMap.get(id.replace(/^league-/, ""));
    if (!league) return res.status(404).json({ meta: null });
    return res.json({ meta: leagueEventsMeta(league, await events()) });
  }
  if (id.startsWith("team-")) {
    const team = favoriteTeamMap.get(id.replace(/^team-/, ""));
    if (!team) return res.status(404).json({ meta: null });
    return res.json({ meta: favoriteTeamMeta(team, await events()) });
  }
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
  version: "2.4.0",
  uptime: process.uptime(),
  cacheEntries: cache.size(),
  providers: providerStatus()
}));

app.get("/poster/:id.svg", async (req,res) => {
  const id = decodeURIComponent(req.params.id).replace(/-bg$/g, "");
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
