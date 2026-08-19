import { artworkForLeague } from "./artwork.js";

const RULES = [
  ["ufc", "ufc"], ["mma", "ufc"], ["nfl", "nfl"], ["nba", "nba"], ["nhl", "nhl"],
  ["mlb", "mlb"], ["ncaa football", "ncaaf"], ["college football", "ncaaf"], ["ncaaf", "ncaaf"],
  ["ncaa basketball", "ncaab"], ["college basketball", "ncaab"], ["ncaab", "ncaab"],
  ["wnba", "wnba"], ["mls", "mls"], ["premier league", "premier-league"], ["epl", "premier-league"],
  ["la liga", "la-liga"], ["formula 1", "f1"], ["f1", "f1"], ["motogp", "motogp"],
  ["boxing", "boxing"], ["atp", "atp"], ["wta", "wta"], ["pga", "pga"], ["rugby", "rugby"],
  ["cricket", "cricket"], ["pdc", "pdc"], ["darts", "pdc"], ["afl", "afl"]
];

function leagueKey(meta) {
  const haystack = [meta?.id, meta?.name, meta?.description, ...(meta?.genres || [])].join(" ").toLowerCase();
  for (const [needle, key] of RULES) if (haystack.includes(needle)) return key;
  return null;
}

function normalizeMeta(meta) {
  if (!meta || typeof meta !== "object") return meta;
  const key = leagueKey(meta);
  const fallback = key ? artworkForLeague(key) : artworkForLeague("nfl");
  const poster = typeof meta.poster === "string" && meta.poster.trim() ? meta.poster : fallback.poster;
  const background = typeof meta.background === "string" && meta.background.trim() ? meta.background : fallback.background;
  const logo = typeof meta.logo === "string" && meta.logo.trim() ? meta.logo : fallback.logo;
  return { ...meta, poster, background, logo, posterShape: meta.posterShape || "landscape" };
}

export function installNuvioArtwork(app) {
  app.use((req, res, next) => {
    const originalJson = res.json.bind(res);
    res.json = payload => {
      try {
        if (payload && Array.isArray(payload.metas)) payload = { ...payload, metas: payload.metas.map(normalizeMeta) };
        if (payload && payload.meta) payload = { ...payload, meta: normalizeMeta(payload.meta) };
      } catch (_) {}
      return originalJson(payload);
    };
    next();
  });
}
