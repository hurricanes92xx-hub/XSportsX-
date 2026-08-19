import http from "node:http";

const PORT = Number(process.env.PORT || 7000);
const UPSTREAM_PORT = Number(process.env.XSPORTSX_PRODUCTION_UPSTREAM_PORT || 7010);
const BASE = process.env.BASE_URL || "https://xsportsx.onrender.com";
const VERSION = "4.4.0";
const ADDON_ID = "com.xsportsx.sports.epg";

function headers(type = "application/json; charset=utf-8") {
  return { "content-type": type, "cache-control": "no-store, no-cache, max-age=0, must-revalidate", "pragma": "no-cache", "expires": "0", "access-control-allow-origin": "*", "x-xsportsx-version": VERSION, "x-xsportsx-addon-id": ADDON_ID };
}
function send(res, status, body, type = "application/json; charset=utf-8") { res.writeHead(status, headers(type)); res.end(body); }

function classify(meta) {
  const text = [meta?.name, meta?.description, ...(meta?.genres || [])].join(" ").toLowerCase();
  const live = /(^|\W)live(\W|$)|🔴/.test(text);
  const soon = /starting soon|⏰/.test(text);
  const ufc = /ufc|mma/.test(text);
  const ncaaf = /ncaaf|ncaa football|college football|cfp|acc network|big ten network|sec network|big 12/.test(text);
  const nfl = /\bnfl\b|football/.test(text);
  const nba = /\bnba\b/.test(text);
  const nhl = /\bnhl\b/.test(text);
  const mlb = /\bmlb\b/.test(text);
  const soccer = /soccer|premier league|la liga|mls/.test(text);
  return { text, live, soon, ufc, ncaaf, nfl, nba, nhl, mlb, soccer };
}

function commandCenterCatalog(metas, mode) {
  let result = metas.filter(Boolean);
  if (mode === "live-now") result = result.filter(m => classify(m).live);
  else if (mode === "starting-soon") result = result.filter(m => classify(m).soon);
  else if (mode === "ufc") result = result.filter(m => classify(m).ufc);
  else if (mode === "ncaaf") result = result.filter(m => classify(m).ncaaf);
  else if (mode === "nfl") result = result.filter(m => classify(m).nfl);
  else if (mode === "nba") result = result.filter(m => classify(m).nba);
  else if (mode === "nhl") result = result.filter(m => classify(m).nhl);
  else if (mode === "mlb") result = result.filter(m => classify(m).mlb);
  else if (mode === "soccer") result = result.filter(m => classify(m).soccer);
  else if (mode === "featured") result = result.filter(m => {
    const c = classify(m); return c.live || c.soon || c.ufc || c.ncaaf || /ranked|cfp|title|playoff|championship|rivalry/i.test(c.text);
  });
  return result.map(m => ({
    ...m,
    type: "channel",
    posterShape: "landscape",
    genres: [...new Set([...(m.genres || []), "Sports Command Center", mode])],
    behaviorHints: { ...(m.behaviorHints || {}), defaultVideoId: m.behaviorHints?.defaultVideoId || m.videos?.[0]?.id }
  })).slice(0, 500);
}

async function upstream(path, init) {
  return fetch(`http://127.0.0.1:${UPSTREAM_PORT}${path}`, init);
}
async function upstreamJson(path) {
  const response = await upstream(path);
  if (!response.ok) throw new Error(`upstream ${response.status}`);
  return response.json();
}

function buildManifest() {
  return {
    id: ADDON_ID,
    version: VERSION,
    name: "XSportsX Sports Command Center",
    description: "Ultimate sports command center with live-first game discovery, starting-soon alerts, featured matchups, league hubs, UFC and NCAA Football intelligence, broadcast networks, artwork, EPG and stream resolution.",
    logo: "https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png",
    background: "https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png",
    resources: [
      { name: "catalog", types: ["channel"] },
      { name: "meta", types: ["channel"], idPrefixes: ["sport:"] },
      { name: "stream", types: ["channel"], idPrefixes: ["sport:"] }
    ],
    types: ["channel"],
    idPrefixes: ["sport:"],
    behaviorHints: { configurable: false, configurationRequired: false },
    liveTv: { enabled: true, name: "XSportsX Sports Live TV", playlist: `${BASE}/live-tv.m3u`, epg: `${BASE}/epg.xml`, guide: `${BASE}/catalog/channel/sports-command-center.json`, refreshSeconds: 60 },
    catalogs: [
      { type: "channel", id: "sports-command-center", name: "🏆 XSPORTSX • SPORTS COMMAND CENTER" },
      { type: "channel", id: "live-now", name: "🔴 LIVE NOW" },
      { type: "channel", id: "starting-soon", name: "⏰ STARTING SOON" },
      { type: "channel", id: "featured", name: "⭐ FEATURED" },
      { type: "channel", id: "sports-epg", name: "📺 ALL SPORTS • EPG" },
      { type: "channel", id: "nfl", name: "🏈 NFL" },
      { type: "channel", id: "ncaaf", name: "🏈 NCAA FOOTBALL" },
      { type: "channel", id: "nba", name: "🏀 NBA" },
      { type: "channel", id: "nhl", name: "🏒 NHL" },
      { type: "channel", id: "mlb", name: "⚾ MLB" },
      { type: "channel", id: "ufc", name: "🥊 UFC COMMAND CENTER" },
      { type: "channel", id: "soccer", name: "⚽ SOCCER" }
    ]
  };
}

async function proxy(req, res) {
  const original = req.url || "/", path = original.split("?")[0], url = new URL(original, BASE);
  if (path === "/manifest.json" || path === "/manifest-4.4.0.json") return send(res, 200, JSON.stringify(buildManifest()));
  if (path === "/health") return send(res, 200, JSON.stringify({ ok: true, version: VERSION, addonId: ADDON_ID, type: "channel", liveTv: true, epg: true, commandCenter: true }));
  if (path === "/live-tv.json") return send(res, 200, JSON.stringify({ id: ADDON_ID, version: VERSION, name: "XSportsX Sports Live TV", playlist: `${BASE}/live-tv.m3u`, epg: `${BASE}/epg.xml`, refreshSeconds: 60, catalog: `${BASE}/catalog/channel/sports-command-center.json`, guide: `${BASE}/catalog/channel/sports-command-center.json` }));
  if (path === "/nuvio.m3u") { const r = await upstream("/live-tv.m3u"); return send(res, r.status, await r.text(), "application/x-mpegURL; charset=utf-8"); }
  if (path === "/nuvio-epg.xml") { const r = await upstream("/epg.xml"); return send(res, r.status, await r.text(), "application/xml; charset=utf-8"); }
  if (path.startsWith("/catalog/channel/")) {
    const id = path.slice("/catalog/channel/".length).replace(/\.json$/, "");
    const source = await upstreamJson("/catalog/channel/sports-epg.json").catch(async () => upstreamJson("/catalog/sport/upcoming.json"));
    if (id === "sports-command-center" || id === "sports-epg") return send(res, 200, JSON.stringify({ metas: commandCenterCatalog(source.metas || [], id === "sports-epg" ? "all" : "featured") }));
    if (["live-now","starting-soon","featured","nfl","ncaaf","nba","nhl","mlb","ufc","soccer"].includes(id)) return send(res, 200, JSON.stringify({ metas: commandCenterCatalog(source.metas || [], id) }));
  }
  const upstreamResponse = await upstream(original, { method: req.method, headers: { ...req.headers, host: `127.0.0.1:${UPSTREAM_PORT}` }, body: req.method === "GET" || req.method === "HEAD" ? undefined : req });
  const type = upstreamResponse.headers.get("content-type") || "application/octet-stream", body = Buffer.from(await upstreamResponse.arrayBuffer());
  res.writeHead(upstreamResponse.status, headers(type)); res.end(body);
}

http.createServer((req, res) => proxy(req, res).catch(error => send(res, 502, JSON.stringify({ error: "production gateway unavailable", detail: String(error?.message || error) })))).listen(PORT, "0.0.0.0", () => console.log(`XSportsX Sports Command Center ${VERSION} production gateway listening on ${PORT}`));
