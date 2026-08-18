const UFC_DATA_URL = process.env.UFC_DATA_URL || "https://www.ufc.com/events?language_content_entity=en";
const UFC_EVENTS_URL = "https://www.ufc.com/events?language_content_entity=en";
const UFC_RANKINGS_URL = process.env.UFC_RANKINGS_URL || "https://www.ufc.com/rankings";
const UFC_ATHLETES_URL = process.env.UFC_ATHLETES_URL || "https://www.ufc.com/athletes";
const TTL_MS = Number(process.env.UFC_DATA_TTL_MS || 300000);
const OFFICIAL_TTL_MS = Number(process.env.UFC_OFFICIAL_TTL_MS || 900000);
const PROFILE_TTL_MS = Number(process.env.UFC_PROFILE_TTL_MS || 21600000);
let cache = { at: 0, data: null };
let officialCache = { at: 0, rankings: [], athletes: [] };
const profileCache = new Map();

function clean(value) { return String(value || "").replace(/\s+/g, " ").trim(); }
function decodeHtml(value) { return clean(String(value || "").replace(/&amp;/g, "&").replace(/&#39;|&apos;/g, "'").replace(/&quot;/g, '"').replace(/&nbsp;/g, " ").replace(/&lt;/g, "<").replace(/&gt;/g, ">")); }
function stripTags(value) { return decodeHtml(String(value || "").replace(/<[^>]+>/g, " ")); }
function slug(value) { return clean(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); }

function normalizeFight(f = {}) {
  const a = f.fighter1 || f.red || f.home || f.a || {};
  const b = f.fighter2 || f.blue || f.away || f.b || {};
  const fighter = x => typeof x === "string" ? { name: clean(x) } : { name: clean(x.name || x.displayName), image: x.image || x.photo || "", country: clean(x.country || x.nationality), record: clean(x.record), rank: clean(x.rank), champion: Boolean(x.champion), profileUrl: x.profileUrl || "" };
  return { bout: clean(f.bout || f.type || f.weightClass), rounds: Number(f.rounds || 3), title: Boolean(f.title || f.isTitleFight || f.championship), mainEvent: Boolean(f.mainEvent || f.main_event), coMain: Boolean(f.coMain || f.co_main), status: clean(f.status || "scheduled").toLowerCase(), result: clean(f.result || f.method), fighter1: fighter(a), fighter2: fighter(b) };
}
function normalizeEvent(e = {}) { return { id: clean(e.id || e.eventId || e.slug || e.url), name: clean(e.name || e.title), date: e.date || e.start || "", venue: clean(e.venue), city: clean(e.city), image: e.image || e.poster || "", officialUrl: e.officialUrl || e.url || UFC_EVENTS_URL, fights: Array.isArray(e.fights || e.card) ? (e.fights || e.card).map(normalizeFight) : [] }; }

async function fetchText(url) {
  const response = await fetch(url, { headers: { accept: "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8", "user-agent": "XSportsX/3.8 (+https://xsportsx.onrender.com)" } });
  if (!response.ok) throw new Error(`UFC source returned ${response.status}`);
  return response.text();
}
async function fetchJson(url) { const response = await fetch(url, { headers: { accept: "application/json", "user-agent": "XSportsX/3.8" } }); if (!response.ok) throw new Error(`UFC data source returned ${response.status}`); return response.json(); }

function parseJsonLd(html) {
  const out = [];
  const re = /<script[^>]+type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi;
  let match;
  while ((match = re.exec(html))) { try { const value = JSON.parse(match[1].trim()); const items = Array.isArray(value) ? value : (Array.isArray(value?.itemListElement) ? value.itemListElement : [value]); for (const item of items) { const obj = item?.item || item; if (obj && (obj['@type'] === 'Event' || obj.name) && obj.name) out.push(obj); } } catch {} }
  return out;
}
function parseOfficialEvents(html) {
  const events = parseJsonLd(html), seen = new Set(), result = [];
  for (const item of events) {
    const name = clean(item.name); if (!name || seen.has(name.toLowerCase())) continue; seen.add(name.toLowerCase());
    const location = item.location || {}, address = location.address || {};
    result.push(normalizeEvent({ id: item.url || name, name, date: item.startDate || item.date, venue: location.name, city: address.addressLocality || address.addressRegion, image: Array.isArray(item.image) ? item.image[0] : item.image, officialUrl: item.url || UFC_EVENTS_URL }));
  }
  return result;
}
function extractAthleteLinks(html, sourceUrl) {
  const out = [], seen = new Set();
  const re = /<a[^>]+href=["'](\/athlete\/[^"'#?]+)[^"']*["'][^>]*>([\s\S]*?)<\/a>/gi;
  let match;
  while ((match = re.exec(html))) {
    const profileUrl = new URL(match[1], "https://www.ufc.com").href;
    const name = stripTags(match[2]); const key = profileUrl.toLowerCase();
    if (!name || seen.has(key)) continue;
    seen.add(key); out.push({ name, profileUrl, sourceUrl, image: "", official: true });
  }
  return out;
}
function extractRankedAthletes(html) {
  return extractAthleteLinks(html, UFC_RANKINGS_URL).map((fighter, index) => ({ ...fighter, rank: null, champion: false, division: "UFC Rankings", position: index + 1 }));
}
async function officialPageData() {
  if (Date.now() - officialCache.at < OFFICIAL_TTL_MS) return officialCache;
  const [rankingsHtml, athletesHtml] = await Promise.all([fetchText(UFC_RANKINGS_URL).catch(() => ""), fetchText(UFC_ATHLETES_URL).catch(() => "")]);
  officialCache = { at: Date.now(), rankings: rankingsHtml ? extractRankedAthletes(rankingsHtml) : officialCache.rankings, athletes: athletesHtml ? extractAthleteLinks(athletesHtml, UFC_ATHLETES_URL) : officialCache.athletes };
  return officialCache;
}
export async function getUfcOfficialRankings() { try { return (await officialPageData()).rankings || []; } catch { return officialCache.rankings || []; } }
export async function getUfcOfficialAthletes() { try { return (await officialPageData()).athletes || []; } catch { return officialCache.athletes || []; } }

function firstMatch(body, patterns) { for (const pattern of patterns) { const m = body.match(pattern); if (m?.[1]) return clean(stripTags(m[1])); } return ""; }
function parseProfileStats(body) {
  const text = stripTags(body);
  const record = firstMatch(body, [/>(\d+\s*-\s*\d+(?:\s*-\s*\d+)?(?:\s*-\s*\d+)?)<\/[^>]+>/i]) || firstMatch(body, [/"record"\s*:\s*"([^"]+)"/i]);
  const division = firstMatch(body, [/"division"\s*:\s*"([^"]+)"/i, />([^<]{3,40})<\/[^>]+>\s*(?:Division|Weight Class)/i]);
  const height = firstMatch(body, [/"height"\s*:\s*"([^"]+)"/i]);
  const reach = firstMatch(body, [/"reach"\s*:\s*"([^"]+)"/i]);
  const stance = firstMatch(body, [/"stance"\s*:\s*"([^"]+)"/i]);
  const ko = firstMatch(body, [/"ko_wins"\s*:\s*"?([0-9]+)"?/i, /"wins_by_knockout"\s*:\s*"?([0-9]+)"?/i]);
  const sub = firstMatch(body, [/"submission_wins"\s*:\s*"?([0-9]+)"?/i, /"wins_by_submission"\s*:\s*"?([0-9]+)"?/i]);
  const sig = firstMatch(body, [/"sig_strikes_per_minute"\s*:\s*"?([^",}]+)"?/i, /"sig_strikes"\s*:\s*"?([^",}]+)"?/i]);
  const td = firstMatch(body, [/"takedown_accuracy"\s*:\s*"?([^",}]+)"?/i]);
  const tdd = firstMatch(body, [/"takedown_defense"\s*:\s*"?([^",}]+)"?/i]);
  return { record, division, height, reach, stance, koWins: ko, submissionWins: sub, significantStrikes: sig, takedownAccuracy: td, takedownDefense: tdd, searchableText: text.slice(0, 1200) };
}
async function enrichAthlete(fighter) {
  if (!fighter?.profileUrl) return fighter;
  const now = Date.now(), cached = profileCache.get(fighter.profileUrl);
  if (cached && now - cached.at < PROFILE_TTL_MS) return { ...fighter, ...cached.value };
  try {
    const body = await fetchText(fighter.profileUrl);
    const stats = parseProfileStats(body);
    const value = { ...fighter, ...stats, official: true };
    profileCache.set(fighter.profileUrl, { at: now, value: stats });
    return value;
  } catch { return fighter; }
}
async function enrichFight(fight) {
  const [a, b] = await Promise.all([enrichAthlete(fight.fighter1), enrichAthlete(fight.fighter2)]);
  return { ...fight, fighter1: a, fighter2: b, comparison: { records: [a.record || "—", b.record || "—"], ranks: [a.rank || "Unranked", b.rank || "Unranked"], weightClass: fight.bout || a.division || b.division || "UFC", titleFight: Boolean(fight.title), rounds: Number(fight.rounds || 3), physical: { height: [a.height || "—", b.height || "—"], reach: [a.reach || "—", b.reach || "—"], stance: [a.stance || "—", b.stance || "—"] }, methods: { ko: [a.koWins || "—", b.koWins || "—"], submission: [a.submissionWins || "—", b.submissionWins || "—"] }, metrics: { significantStrikes: [a.significantStrikes || "—", b.significantStrikes || "—"], takedownAccuracy: [a.takedownAccuracy || "—", b.takedownAccuracy || "—"], takedownDefense: [a.takedownDefense || "—", b.takedownDefense || "—"] } } };
}

export async function getUfcData() {
  if (cache.data && Date.now() - cache.at < TTL_MS) return cache.data;
  try {
    let data = [];
    if (UFC_DATA_URL.startsWith("http") && UFC_DATA_URL.includes("ufc.com")) data = parseOfficialEvents(await fetchText(UFC_EVENTS_URL));
    else if (UFC_DATA_URL) { const raw = await fetchJson(UFC_DATA_URL); const list = Array.isArray(raw) ? raw : (raw.events || raw.data || []); data = list.map(normalizeEvent).filter(e => e.name); }
    const enriched = [];
    for (const event of data.slice(0, 12)) {
      const fights = [];
      for (const fight of event.fights || []) fights.push(await enrichFight(fight));
      enriched.push({ ...event, fights });
    }
    cache = { at: Date.now(), data: enriched }; return enriched;
  } catch {
    try { const data = parseOfficialEvents(await fetchText(UFC_EVENTS_URL)); cache = { at: Date.now(), data }; return data; } catch { return cache.data || []; }
  }
}
export function enrichUfcEvent(event, ufcEvents) { const name = clean(event?.title).toLowerCase(); const match = ufcEvents.find(x => name.includes(x.name.toLowerCase()) || x.name.toLowerCase().includes(name)); return { event, detail: match || null }; }
export function ufcSections(detail) { const fights = detail?.fights || []; return { mainCard: fights.filter(f => f.mainEvent || f.coMain || f.title || f.bout.toLowerCase().includes("main card")), prelims: fights.filter(f => !f.mainEvent && !f.coMain && !f.title && !f.bout.toLowerCase().includes("main card")) }; }
