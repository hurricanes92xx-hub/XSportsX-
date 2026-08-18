const UFC_DATA_URL = process.env.UFC_DATA_URL || "";
const TTL_MS = Number(process.env.UFC_DATA_TTL_MS || 300000);
let cache = { at: 0, data: null };

function clean(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function normalizeFight(f = {}) {
  const a = f.fighter1 || f.red || f.home || f.a || {};
  const b = f.fighter2 || f.blue || f.away || f.b || {};
  const fighter = x => typeof x === "string" ? { name: clean(x) } : {
    name: clean(x.name || x.displayName),
    image: x.image || x.photo || "",
    country: clean(x.country || x.nationality),
    record: clean(x.record),
    rank: clean(x.rank),
    champion: Boolean(x.champion)
  };
  return {
    bout: clean(f.bout || f.type || f.weightClass),
    rounds: Number(f.rounds || 3),
    title: Boolean(f.title || f.isTitleFight || f.championship),
    mainEvent: Boolean(f.mainEvent || f.main_event),
    coMain: Boolean(f.coMain || f.co_main),
    status: clean(f.status || "scheduled").toLowerCase(),
    result: clean(f.result || f.method),
    fighter1: fighter(a),
    fighter2: fighter(b)
  };
}

function normalizeEvent(e = {}) {
  return {
    id: clean(e.id || e.eventId || e.slug),
    name: clean(e.name || e.title),
    date: e.date || e.start || "",
    venue: clean(e.venue),
    city: clean(e.city),
    image: e.image || e.poster || "",
    officialUrl: e.officialUrl || e.url || "https://www.ufc.com/events",
    fights: Array.isArray(e.fights || e.card) ? (e.fights || e.card).map(normalizeFight) : []
  };
}

async function fetchJson(url) {
  const response = await fetch(url, { headers: { accept: "application/json", "user-agent": "XSportsX/3.4" } });
  if (!response.ok) throw new Error(`UFC data source returned ${response.status}`);
  return response.json();
}

export async function getUfcData() {
  if (cache.data && Date.now() - cache.at < TTL_MS) return cache.data;
  if (!UFC_DATA_URL) return [];
  try {
    const raw = await fetchJson(UFC_DATA_URL);
    const list = Array.isArray(raw) ? raw : (raw.events || raw.data || []);
    cache = { at: Date.now(), data: list.map(normalizeEvent).filter(e => e.name) };
    return cache.data;
  } catch {
    return cache.data || [];
  }
}

export function enrichUfcEvent(event, ufcEvents) {
  const name = clean(event?.title).toLowerCase();
  const match = ufcEvents.find(x => name.includes(x.name.toLowerCase()) || x.name.toLowerCase().includes(name));
  return { event, detail: match || null };
}

export function ufcSections(detail) {
  const fights = detail?.fights || [];
  return {
    mainCard: fights.filter(f => f.mainEvent || f.coMain || f.title || f.bout.toLowerCase().includes("main card")),
    prelims: fights.filter(f => !f.mainEvent && !f.coMain && !f.title && !f.bout.toLowerCase().includes("main card"))
  };
}
