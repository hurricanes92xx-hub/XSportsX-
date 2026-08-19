const RAW_BASE = "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/main/";
const CDN_BASE = "https://cdn.jsdelivr.net/gh/hurricanes92xx-hub/XSportsX-@main/";

const ASSETS = {
  nfl: "nfl.gif",
  nba: "nba.gif",
  nhl: "nhl.gif",
  mlb: "mlb.gif",
  ncaaf: "ncaaf.gif",
  ncaab: "ncaab.gif",
  wnba: "wnba.gif",
  mls: "mls.gif",
  "premier-league": "premier-league.gif",
  "la-liga": "la-liga.gif",
  f1: "f1.gif",
  motogp: "motogp.gif",
  ufc: "ufc.gif",
  boxing: "boxing.gif",
  atp: "atp.gif",
  wta: "wta.gif",
  pga: "pga.gif",
  rugby: "rugby.gif",
  cricket: "cricket.gif",
  pdc: "pdc.gif",
  afl: "afl.gif",
};

export function publicAsset(name) {
  const file = ASSETS[name] || ASSETS.nfl;
  return `${RAW_BASE}${file}`;
}

export function cdnAsset(name) {
  const file = ASSETS[name] || ASSETS.nfl;
  return `${CDN_BASE}${file}`;
}

export function artworkForEvent(event) {
  const sport = String(event?.sport || "").toLowerCase();
  const league = String(event?.league || "").toLowerCase();
  const key = ASSETS[sport] ? sport : (ASSETS[league] ? league : "nfl");
  const fallback = publicAsset(key);
  return {
    poster: fallback,
    background: fallback,
    logo: fallback,
    posterShape: "landscape",
  };
}

export function artworkForLeague(id) {
  const key = ASSETS[id] ? id : "nfl";
  const url = publicAsset(key);
  return { poster: url, background: url, logo: url, posterShape: "landscape" };
}
