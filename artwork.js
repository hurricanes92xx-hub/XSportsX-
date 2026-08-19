const RAW_BASE = "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/main/";
const CDN_BASE = "https://cdn.jsdelivr.net/gh/hurricanes92xx-hub/XSportsX-@main/";

const ASSETS = {
  nfl: "nfl.gif", nba: "nba.gif", nhl: "nhl.gif", mlb: "mlb.gif",
  ncaaf: "ncaaf.gif", ncaab: "ncaab.gif", wnba: "wnba.gif", mls: "mls.gif",
  "premier-league": "premier-league.gif", "la-liga": "la-liga.gif",
  f1: "f1.gif", motogp: "motogp.gif", ufc: "ufc.gif", boxing: "boxing.gif",
  atp: "atp.gif", wta: "wta.gif", pga: "pga.gif", rugby: "rugby.gif",
  cricket: "cricket.gif", pdc: "pdc.gif", afl: "afl.gif"
};

const ALIASES = {
  "nfl": "nfl", "national football league": "nfl",
  "nba": "nba", "national basketball association": "nba",
  "nhl": "nhl", "national hockey league": "nhl",
  "mlb": "mlb", "major league baseball": "mlb",
  "ncaaf": "ncaaf", "ncaa football": "ncaaf", "college football": "ncaaf",
  "ncaab": "ncaab", "ncaa basketball": "ncaab", "college basketball": "ncaab",
  "wnba": "wnba", "mls": "mls", "major league soccer": "mls",
  "epl": "premier-league", "premier league": "premier-league",
  "la liga": "la-liga", "laliga": "la-liga",
  "formula 1": "f1", "formula one": "f1", "f1": "f1",
  "motogp": "motogp", "ufc": "ufc", "mma": "ufc", "boxing": "boxing",
  "atp": "atp", "atp tennis": "atp", "wta": "wta", "wta tennis": "wta",
  "pga": "pga", "pga golf": "pga", "rugby": "rugby", "cricket": "cricket",
  "pdc": "pdc", "darts": "pdc", "afl": "afl"
};

function normalize(value) {
  return String(value || "").trim().toLowerCase().replace(/[•|]/g, " ").replace(/\s+/g, " ");
}

export function resolveLeagueKey(eventOrId) {
  if (typeof eventOrId === "string") {
    const value = normalize(eventOrId);
    return ALIASES[value] || (ASSETS[value] ? value : "nfl");
  }
  const values = [eventOrId?.league, eventOrId?.competition, eventOrId?.sport, eventOrId?.category];
  for (const value of values) {
    const normalized = normalize(value);
    if (ALIASES[normalized]) return ALIASES[normalized];
    if (ASSETS[normalized]) return normalized;
  }
  const text = normalize(eventOrId?.title);
  for (const [alias, key] of Object.entries(ALIASES)) {
    if (alias.length > 3 && text.includes(alias)) return key;
  }
  return "nfl";
}

export function publicAsset(name) {
  const key = resolveLeagueKey(name);
  return `${RAW_BASE}${ASSETS[key]}`;
}

export function cdnAsset(name) {
  const key = resolveLeagueKey(name);
  return `${CDN_BASE}${ASSETS[key]}`;
}

export function artworkForEvent(event) {
  const url = publicAsset(event);
  return { poster:url, background:url, logo:url, posterShape:"landscape" };
}

export function artworkForLeague(id) {
  const url = publicAsset(id);
  return { poster:url, background:url, logo:url, posterShape:"landscape" };
}
