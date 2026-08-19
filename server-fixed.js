import express from "express";
import { getEvents, streamsFor, newsStreamsForChannel, providerStatus } from "./providers.js";
import { TTLCache } from "./core.js";
import { leagueVisual, gameVisual } from "./visuals.js";
import { artworkForEvent, artworkForLeague } from "./artwork.js";
import { installNuvioArtwork } from "./nuvio-artwork-middleware.js";
import { enrichNcaafEvents, cfpWatchEvents, cfpWatchMeta } from "./cfp-watch.js";
import fs from "node:fs";
import path from "node:path";

const app = express();
installNuvioArtwork(app);
const PORT = Number(process.env.PORT || 7000);
const BASE_URL = process.env.BASE_URL || `http://localhost:${PORT}`;
const cache = new TTLCache();
const EVENT_REFRESH_MS = Number(process.env.EVENT_REFRESH_MS || 30000);
const DEFAULT_TZ = process.env.DEFAULT_TIMEZONE || "UTC";
const APP_VERSION = "3.9.7";
let eventRefreshPromise = null;

const LEAGUES = [
  ["nfl","NFL","football","nfl.gif"],["nba","NBA","basketball","nba.gif"],["nhl","NHL","hockey","nhl.gif"],["mlb","MLB","baseball","mlb.gif"],
  ["ncaaf","NCAA Football","football","ncaaf.gif"],["ncaab","NCAA Basketball","basketball","ncaab.gif"],["wnba","WNBA","basketball","wnba.gif"],["mls","MLS","soccer","mls.gif"],
  ["premier-league","Premier League","soccer","premier-league.gif"],["la-liga","La Liga","soccer","la-liga.gif"],["f1","Formula 1","racing","f1.gif"],["motogp","MotoGP","racing","motogp.gif"],
  ["ufc","UFC","mma","ufc.gif"],["boxing","Boxing","boxing","boxing.gif"],["atp","ATP Tennis","tennis","atp.gif"],["wta","WTA Tennis","tennis","wta.gif"],
  ["pga","PGA Golf","golf","pga.gif"],["rugby","Rugby","rugby","rugby.gif"],["cricket","Cricket","cricket","cricket.gif"],["pdc","Darts","darts","pdc.gif"],["afl","AFL","football","afl.gif"]
].map(([id,name,sport,asset]) => ({ id, name, sport, asset }));
const leagueMap = new Map(LEAGUES.map(x => [x.id, x]));

const FAVORITE_TEAMS = [
  { id:"miami-hurricanes-football", name:"Miami Hurricanes Football", sport:"ncaaf", aliases:["Miami Hurricanes","Miami (FL) Hurricanes"] },
  { id:"miami-hurricanes-basketball", name:"Miami Hurricanes Basketball", sport:"ncaab", aliases:["Miami Hurricanes","Miami (FL) Hurricanes"] },
  { id:"miami-dolphins", name:"Miami Dolphins", sport:"nfl", aliases:["Miami Dolphins"] },
  { id:"miami-heat", name:"Miami Heat", sport:"nba", aliases:["Miami Heat"] },
  { id:"tampa-bay-lightning", name:"Tampa Bay Lightning", sport:"nhl", aliases:["Tampa Bay Lightning"] }
];
const favoriteTeamMap = new Map(FAVORITE_TEAMS.map(x => [x.id, x]));

const SPORTS_NEWS_CHANNELS = [
  {id:"espn",name:"ESPN",network:"ESPN",logo:"espn.gif"},{id:"nfl-network",name:"NFL Network",network:"NFL Network",logo:"nfl.gif"},
  {id:"espn2",name:"ESPN2",network:"ESPN2",logo:"espn.gif"},{id:"cbs-sports-hq",name:"CBS Sports HQ",network:"CBS Sports",logo:"mlb.gif"},
  {id:"fox-sports",name:"FOX Sports",network:"FOX Sports",logo:"nfl.gif"},{id:"mlb-network",name:"MLB Network",network:"MLB Network",logo:"mlb.gif"},
  {id:"nba-tv",name:"NBA TV",network:"NBA TV",logo:"nba.gif"},{id:"nhl-network",name:"NHL Network",network:"NHL Network",logo:"nhl.gif"}
];
const newsChannelMap = new Map(SPORTS_NEWS_CHANNELS.map(x => [x.id, x]));
const POPULAR_LEAGUES = new Set(["NFL","NBA","NHL","MLB","NCAAF","NCAAB","MLS","EPL","UFC","F1"]);
const PUBLIC_REPO_ASSET_BASE = "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/main/";
const CDN_ASSET_BASE = "https://cdn.jsdelivr.net/gh/hurricanes92xx-hub/XSportsX-@main/";

// Use a public CDN directly for static posters. This avoids Nuvio/device-specific
// failures fetching GIFs through the Render process and keeps cards independent of BASE_URL.
const leaguePoster = id => artworkForLeague(id).poster;
const teamPoster = id => artworkForLeague(id).poster;
const leagueBackground = id => `${BASE_URL}/visuals/league/${encodeURIComponent(id)}.svg`;
const gamePoster = id => `${BASE_URL}/visuals/game/${encodeURIComponent(id)}.svg`;

function scoreText(e) {
  if (e?.home?.score == null || e?.away?.score == null) return "";
  return ` • ${e.away.short || e.away.name} ${e.away.score} — ${e.home.score} ${e.home.short || e.home.name}`;
}
function eventPopularity(e) {
  let score = e?.state === "in" ? 100 : 0;
  const start = new Date(e?.start || 0).getTime();
  const delta = start - Date.now();
  if (delta > 0 && delta <= 30 * 60_000) score += 60;
  else if (delta > 0 && delta <= 2 * 60 * 60_000) score += 30;
  if (POPULAR_LEAGUES.has(String(e?.league || "").toUpperCase())) score += 20;
  if (e?.broadcast?.length) score += 10;
  if (e?.home?.score != null) score += 5;
  return score;
}
function sortEvents(events) { return [...events].sort((a,b) => eventPopularity(b) - eventPopularity(a) || new Date(a.start || 0) - new Date(b.start || 0)); }
function gameOverview(e) {
  const parts = [e?.detail || e?.league];
  if (e?.broadcast?.length) parts.push(e.broadcast.join(", "));
  if (e?.venue) parts.push(e.venue);
  return parts.filter(Boolean).join(" • ");
}
function gameTitle(e) { return `${e?.state === "in" ? "🔴 LIVE • " : ""}${e?.title || "Sports Event"}${scoreText(e)}`; }
function videoFor(e) {
  const art = artworkForEvent(e);
  return { id:`sport:game-${e.eventId}`, title:gameTitle(e), released:e.start, thumbnail:art.poster, overview:gameOverview(e) };
}

function sportsNewsHeaderMeta() {
  return { id:"sport:news-header", type:"sport", name:"🏟️ SPORTS NEWS", poster:leaguePoster("nfl"), background:leagueBackground("nfl"), description:"English-language sports news and analysis from ESPN, NFL Network, ESPN2, CBS Sports HQ, FOX Sports, MLB Network, NBA TV and NHL Network.", genres:["Sports","News","English"], behaviorHints:{} };
}
function newsChannelMeta(ch, configured = false) {
  const logoId = ch.logo.replace(/\.gif$/, "");
  return { id:`sport:news-${ch.id}`, type:"sport", name:ch.name, poster:leaguePoster(logoId), background:leagueBackground(logoId), description:`${ch.name} • ${configured ? "IPTV source found" : "No matching IPTV source found"}`, genres:["Sports","News",ch.network], behaviorHints:{} };
}
function favoriteTeamMatches(team, all) {
  return all.filter(e => {
    if (e.sport !== team.sport) return false;
    const names = [e.home?.name,e.home?.short,e.away?.name,e.away?.short].filter(Boolean).map(x => String(x).toLowerCase());
    return team.aliases.some(alias => names.some(n => n === alias.toLowerCase() || n.includes(alias.toLowerCase())));
  });
}
function favoriteTeamMeta(team, all) {
  const matches = sortEvents(favoriteTeamMatches(team, all));
  const videos = matches.slice(0,100).map(videoFor);
  const live = matches.filter(e => e.state === "in").length;
  return { id:`sport:team-${team.id}`, type:"sport", name:team.name, poster:teamPoster(team.id), background:teamPoster(team.id), description:`${live ? `${live} LIVE NOW • ` : ""}${matches.length} event${matches.length === 1 ? "" : "s"}`, genres:["Sports","Favorite Teams",team.sport], videos, behaviorHints:{defaultVideoId:videos[0]?.id} };
}
function eventMeta(e) {
  const art = artworkForEvent(e);
  return { id:e.id, type:"sport", name:e.title, poster:art.poster, background:art.background, logo:art.logo, posterShape:art.posterShape, description:`${e.state === "in" ? "🔴 LIVE • " : ""}${gameOverview(e)}${scoreText(e)}`, genres:["Sports",e.sport,e.league].filter(Boolean), releaseInfo:e.start ? new Date(e.start).toLocaleString() : "", videos:[videoFor(e)], behaviorHints:{defaultVideoId:e.id} };
}
function gameCenterMeta(e) {
  const video = videoFor(e);
  const art = artworkForEvent(e);
  video.title = `▶ WATCH • ${e.title}${scoreText(e)}`;
  video.overview = `${e.state === "in" ? "LIVE NOW • " : ""}${gameOverview(e)}`;
  return { id:`sport:game-${e.eventId}`, type:"sport", name:`🏟️ ${e.title}`, poster:art.poster, background:art.background, logo:art.logo, posterShape:art.posterShape, description:`${e.state === "in" ? "🔴 LIVE • " : ""}${gameOverview(e)}${scoreText(e)}`, genres:["Sports","Game Center",e.sport,e.league].filter(Boolean), releaseInfo:e.start ? new Date(e.start).toLocaleString() : "", videos:[video], behaviorHints:{defaultVideoId:e.id} };
}
function leagueEventsMeta(league, all) {
  const matches = sortEvents(all.filter(e => e.sport === league.id || String(e.league || "").toLowerCase() === league.id.toLowerCase()));
  const videos = matches.slice(0,100).map(videoFor);
  const live = matches.filter(e => e.state === "in").length;
  return { id:`sport:league-${league.id}`, type:"sport", name:league.name, poster:leaguePoster(league.id), background:leagueBackground(league.id), description:`${live ? `${live} LIVE NOW • ` : ""}${matches.length} scheduled event${matches.length === 1 ? "" : "s"}`, genres:["Sports",league.sport,league.name].filter(Boolean), videos, behaviorHints:{defaultVideoId:videos[0]?.id} };
}
async function events() {
  const cached = cache.get("events:active");
  if (cached) return cached;
  if (eventRefreshPromise) return eventRefreshPromise;
  eventRefreshPromise = (async () => {
    try {
      const raw = await getEvents({days:2});
      return cache.set("events:active", await enrichNcaafEvents(raw), EVENT_REFRESH_MS);
    } finally { eventRefreshPromise = null; }
  })();
  return eventRefreshPromise;
}
function filterCatalog(all, id) {
  const now = Date.now();
  if (id === "live-now") return sortEvents(all.filter(e => e.state === "in"));
  if (id === "starting-soon") return sortEvents(all.filter(e => { const t = new Date(e.start || 0).getTime(); return t > now && t <= now + 120 * 60_000; }));
  if (id === "upcoming") return sortEvents(all.filter(e => new Date(e.start || 0).getTime() > now));
  if (id === "today") {
    const fmt = new Intl.DateTimeFormat("en-US", {timeZone:DEFAULT_TZ,year:"numeric",month:"2-digit",day:"2-digit"});
    const today = fmt.format(new Date());
    return sortEvents(all.filter(e => fmt.format(new Date(e.start || 0)) === today));
  }
  if (id === "favorites") return sortEvents(all);
  const favorite = favoriteTeamMap.get(id);
  if (favorite) return sortEvents(favoriteTeamMatches(favorite, all));
  return sortEvents(all.filter(e => e.sport === id || String(e.league || "").toLowerCase() === id.toLowerCase()));
}

app.use(express.static("public"));
app.get("/manifest.json", (_, res) => {
  const manifest = JSON.parse(fs.readFileSync(path.join(process.cwd(), "manifest.json"), "utf8"));
  manifest.version = APP_VERSION;
  manifest.logo = `${CDN_ASSET_BASE}nfl.gif`;
  manifest.background = `${CDN_ASSET_BASE}nfl.gif`;
  res.set("Cache-Control", "no-store, no-cache, must-revalidate").json(manifest);
});

async function servePublicGif(req, res) {
  const filename = req.params.file;
  if (!/^[a-z0-9-]+\.gif$/i.test(filename)) return res.status(400).end();
  const key = `asset:${filename}`;
  const cached = cache.get(key);
  if (cached) return res.set("Cache-Control","public,max-age=86400").type("gif").send(cached);
  try {
    const response = await fetch(`${PUBLIC_REPO_ASSET_BASE}${encodeURIComponent(filename)}`);
    if (!response.ok) return res.status(404).end();
    const data = Buffer.from(await response.arrayBuffer());
    cache.set(key, data, 86400000);
    return res.set("Cache-Control","public,max-age=86400").type("gif").send(data);
  } catch { return res.status(502).end(); }
}
app.get("/leagues/:file", servePublicGif);
app.get("/teams/:file", servePublicGif);
app.get("/visuals/league/:id.svg", (req,res) => {
  const id = decodeURIComponent(req.params.id);
  if (!leagueMap.has(id)) return res.status(404).end();
  res.set("Cache-Control","public,max-age=3600").type("image/svg+xml").send(leagueVisual(id, BASE_URL, leaguePoster(id)));
});
app.get("/visuals/game/:id.svg", async (req,res) => {
  const id = decodeURIComponent(req.params.id);
  const e = (await events()).find(x => x.eventId === id);
  if (!e) return res.status(404).end();
  res.set("Cache-Control", e.state === "in" ? "public,max-age=15" : "public,max-age=300").type("image/svg+xml").send(gameVisual(e, BASE_URL));
});

app.get("/catalog/sport/sports-leagues.json", async (_,res) => {
  try { const all = await events(); res.json({metas:LEAGUES.map(l => leagueEventsMeta(l,all))}); }
  catch { res.status(502).json({metas:[]}); }
});
app.get("/catalog/sport/favorite-teams.json", async (_,res) => {
  try { const all = await events(); res.json({metas:FAVORITE_TEAMS.map(t => favoriteTeamMeta(t,all))}); }
  catch { res.status(502).json({metas:[]}); }
});
app.get("/catalog/sport/sports-news.json", async (_,res) => {
  try {
    const streams = await Promise.all(SPORTS_NEWS_CHANNELS.map(c => newsStreamsForChannel(c.id)));
    res.json({metas:[sportsNewsHeaderMeta(), ...SPORTS_NEWS_CHANNELS.map((c,i) => newsChannelMeta(c, streams[i].length > 0))]});
  } catch {
    res.json({metas:[sportsNewsHeaderMeta(), ...SPORTS_NEWS_CHANNELS.map(c => newsChannelMeta(c,false))]});
  }
});
app.get("/catalog/sport/:catalog.json", async (req,res) => {
  try {
    const all = await events();
    if (req.params.catalog === "cfp-watch") return res.json({metas:cfpWatchEvents(all).map(e => cfpWatchMeta(e, gamePoster, gameOverview, scoreText, videoFor))});
    res.json({metas:filterCatalog(all, req.params.catalog).map(eventMeta)});
  } catch { res.status(502).json({metas:[]}); }
});

app.get("/meta/sport/:id.json", async (req,res) => {
  const id = req.params.id.replace(/^sport:/, "");
  try {
    if (id === "news-header") return res.json({meta:sportsNewsHeaderMeta()});
    if (id.startsWith("news-")) {
      const ch = newsChannelMap.get(id.slice(5));
      if (!ch) return res.status(404).json({meta:null});
      const streams = await newsStreamsForChannel(ch.id);
      return res.json({meta:newsChannelMeta(ch,streams.length > 0)});
    }
    const all = await events();
    if (id.startsWith("cfp-")) {
      const e = all.find(x => x.eventId === id.slice(4));
      return e && cfpWatchEvents([e]).length ? res.json({meta:cfpWatchMeta(e, gamePoster, gameOverview, scoreText, videoFor)}) : res.status(404).json({meta:null});
    }
    if (id.startsWith("game-")) {
      const e = all.find(x => x.eventId === id.slice(5));
      return e ? res.json({meta:gameCenterMeta(e)}) : res.status(404).json({meta:null});
    }
    if (id.startsWith("league-")) {
      const league = leagueMap.get(id.slice(7));
      return league ? res.json({meta:leagueEventsMeta(league,all)}) : res.status(404).json({meta:null});
    }
    if (id.startsWith("team-")) {
      const team = favoriteTeamMap.get(id.slice(5));
      return team ? res.json({meta:favoriteTeamMeta(team,all)}) : res.status(404).json({meta:null});
    }
    const e = all.find(x => x.eventId === id);
    return e ? res.json({meta:gameCenterMeta(e)}) : res.status(404).json({meta:null});
  } catch { return res.status(502).json({meta:null}); }
});

app.get("/stream/sport/:id.json", async (req,res) => {
  const id = req.params.id.replace(/^sport:/, "");
  try {
    if (id === "news-header") return res.json({streams:[]});
    if (id.startsWith("news-")) {
      const ch = newsChannelMap.get(id.slice(5));
      return res.json({streams:ch ? await newsStreamsForChannel(ch.id) : []});
    }
    const e = (await events()).find(x => x.eventId === (id.startsWith("game-") ? id.slice(5) : id));
    return e ? res.json({streams:await streamsFor(e)}) : res.json({streams:[]});
  } catch { return res.json({streams:[]}); }
});

app.get("/sources/status", (_,res) => res.json(providerStatus()));
app.get("/stats", (_,res) => res.json({version:APP_VERSION,cache:cache.statsSummary(),providers:providerStatus()}));
app.get("/health", (_,res) => res.json({ok:true,version:APP_VERSION,uptime:process.uptime()}));

app.listen(PORT, () => console.log(`XSportsX listening on ${PORT}`));
