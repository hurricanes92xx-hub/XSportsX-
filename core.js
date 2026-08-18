export class TTLCache {
  constructor() { this.map = new Map(); }
  get(key) {
    const hit = this.map.get(key);
    if (!hit || hit.expires < Date.now()) { this.map.delete(key); return null; }
    return hit.value;
  }
  set(key, value, ttl) {
    this.map.set(key, { value, expires: Date.now() + ttl });
    return value;
  }
  clear() { this.map.clear(); }
  size() { return this.map.size; }
}

export class CircuitBreaker {
  constructor({ failureThreshold = 3, cooldownMs = 30000 } = {}) {
    this.failureThreshold = failureThreshold;
    this.cooldownMs = cooldownMs;
    this.state = new Map();
  }
  isOpen(name) {
    const s = this.state.get(name);
    if (!s) return false;
    if (s.openUntil && s.openUntil <= Date.now()) {
      this.state.set(name, { failures: 0, openUntil: 0 });
      return false;
    }
    return Boolean(s.openUntil);
  }
  success(name) { this.state.set(name, { failures: 0, openUntil: 0 }); }
  failure(name) {
    const s = this.state.get(name) || { failures: 0, openUntil: 0 };
    s.failures += 1;
    if (s.failures >= this.failureThreshold) s.openUntil = Date.now() + this.cooldownMs;
    this.state.set(name, s);
  }
  status() {
    return Object.fromEntries([...this.state].map(([k, v]) => [k, {...v, open: Boolean(v.openUntil && v.openUntil > Date.now())}]));
  }
}

export function tokenize(text = "") {
  return String(text).toLowerCase().replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, " ").split(/\s+/).filter(Boolean);
}

export function normalizeName(text = "") {
  return tokenize(text).join(" ");
}

export function similarity(a = "", b = "") {
  const A = new Set(tokenize(a));
  const B = new Set(tokenize(b));
  if (!A.size || !B.size) return 0;
  let common = 0;
  for (const x of A) if (B.has(x)) common++;
  return common / Math.max(A.size, B.size);
}

export function eventKey(event) {
  const ids = [event?.home?.short, event?.away?.short].filter(Boolean).sort();
  const t = event?.start ? new Date(event.start).toISOString().slice(0, 13) : "unknown";
  return `${normalizeName(event?.league || "")}:${ids.join("-")}:${t}`;
}

export function matchScore(channel, event) {
  const hay = normalizeName(`${channel.name} ${channel.group} ${channel.id}`);
  const home = normalizeName(`${event?.home?.name} ${event?.home?.short}`);
  const away = normalizeName(`${event?.away?.name} ${event?.away?.short}`);
  const league = normalizeName(event?.league || "");
  let score = 0;
  if (home && hay.includes(home)) score += 30;
  if (away && hay.includes(away)) score += 30;
  if (event?.home?.short && hay.includes(normalizeName(event.home.short))) score += 20;
  if (event?.away?.short && hay.includes(normalizeName(event.away.short))) score += 20;
  if (league && hay.includes(league)) score += 10;
  score += Math.round(similarity(channel.name, event.title) * 20);
  return Math.min(100, score);
}

export function rankStreams(streams) {
  const quality = (s) => {
    const x = `${s.name} ${s.description} ${s.url}`.toLowerCase();
    if (x.includes("4k") || x.includes("2160")) return 40;
    if (x.includes("1080") || x.includes("fhd")) return 30;
    if (x.includes("720") || x.includes("hd")) return 20;
    return 10;
  };
  return [...streams].sort((a,b) =>
    (b.score || 0) - (a.score || 0) ||
    quality(b) - quality(a) ||
    (b.priority || 0) - (a.priority || 0)
  );
}

export async function fetchWithTimeout(url, options = {}, timeoutMs = 9000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, {
      redirect: "follow",
      ...options,
      signal: controller.signal,
      headers: {
        "User-Agent": "XSportsX/2.0 Nuvio addon",
        ...(options.headers || {})
      }
    });
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchText(url, options = {}, timeoutMs = 9000) {
  const r = await fetchWithTimeout(url, options, timeoutMs);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.text();
}

export async function fetchJson(url, options = {}, timeoutMs = 9000) {
  const r = await fetchWithTimeout(url, options, timeoutMs);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}
