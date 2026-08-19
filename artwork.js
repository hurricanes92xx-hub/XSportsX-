const ESPN = "https://a.espncdn.com/i/teamlogos/leagues/500/";
const GENERIC = "https://commons.wikimedia.org/wiki/Special:Redirect/file/ESPN_logo.png";
const UFC_PNG = "https://upload.wikimedia.org/wikipedia/commons/4/4f/UFC_Logo.png";
const NCAA_PNG = "https://commons.wikimedia.org/wiki/Special:Redirect/file/NCAA_Football_wordmark_color.svg?width=960";

const ASSETS = {
  nfl: `${ESPN}nfl.png`, nba: `${ESPN}nba.png`, nhl: `${ESPN}nhl.png`, mlb: `${ESPN}mlb.png`,
  ncaaf: NCAA_PNG, ncaab: `${ESPN}ncaab.png`, wnba: `${ESPN}wnba.png`, mls: `${ESPN}mls.png`,
  "premier-league": `${ESPN}eng.1.png`, "la-liga": `${ESPN}esp.1.png`, f1: `${ESPN}f1.png`,
  motogp: `${ESPN}motogp.png`, ufc: UFC_PNG, boxing: GENERIC, atp: `${ESPN}atp.png`,
  wta: `${ESPN}wta.png`, pga: `${ESPN}pga.png`, rugby: GENERIC, cricket: GENERIC,
  pdc: GENERIC, afl: GENERIC
};

const ALIASES = {
  nfl:"nfl", "national football league":"nfl", nba:"nba", "national basketball association":"nba",
  nhl:"nhl", "national hockey league":"nhl", mlb:"mlb", "major league baseball":"mlb",
  ncaaf:"ncaaf", "ncaa football":"ncaaf", "college football":"ncaaf", ncaab:"ncaab",
  "ncaa basketball":"ncaab", "college basketball":"ncaab", wnba:"wnba", mls:"mls",
  "major league soccer":"mls", epl:"premier-league", "premier league":"premier-league",
  "la liga":"la-liga", laliga:"la-liga", "formula 1":"f1", "formula one":"f1", f1:"f1",
  motogp:"motogp", ufc:"ufc", mma:"ufc", boxing:"boxing", atp:"atp", "atp tennis":"atp",
  wta:"wta", "wta tennis":"wta", pga:"pga", "pga golf":"pga", rugby:"rugby",
  cricket:"cricket", pdc:"pdc", darts:"pdc", afl:"afl"
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
  return ASSETS[resolveLeagueKey(name)] || ASSETS.nfl;
}

export function cdnAsset(name) {
  return publicAsset(name);
}

function usablePng(url) {
  return typeof url === "string" && /^https:\/\//i.test(url) && /\.png(?:$|[?#])/i.test(url);
}

export function artworkForEvent(event) {
  const key = resolveLeagueKey(event);
  const team = event?.home?.logo || event?.home?.image || event?.away?.logo || event?.away?.image;
  const poster = usablePng(team) ? team : publicAsset(key);
  return { poster, background: publicAsset(key), logo: publicAsset(key), posterShape: "square" };
}

export function artworkForLeague(id) {
  const url = publicAsset(id);
  return { poster: url, background: url, logo: url, posterShape: "square" };
}
