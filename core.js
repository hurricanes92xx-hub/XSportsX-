export class TTLCache {
  constructor() { this.map = new Map(); this.stats = { hits: 0, misses: 0 }; }
  get(key) {
    const hit = this.map.get(key);
    if (!hit || hit.expires < Date.now()) { this.stats.misses++; return null; }
    this.stats.hits++;
    return hit.value;
  }
  getStale(key) { return this.map.get(key)?.value ?? null; }
  set(key, value, ttl) { this.map.set(key, { value, expires: Date.now() + ttl }); return value; }
  clear() { this.map.clear(); }
  size() { return this.map.size; }
  statsSummary() { return { ...this.stats, entries: this.map.size }; }
}

export class CircuitBreaker {
  constructor({ failureThreshold = 3, cooldownMs = 30000 } = {}) { this.failureThreshold = failureThreshold; this.cooldownMs = cooldownMs; this.state = new Map(); }
  isOpen(name) {
    const s = this.state.get(name); if (!s) return false;
    if (s.openUntil && s.openUntil <= Date.now()) { this.state.set(name, { failures: 0, openUntil: 0 }); return false; }
    return Boolean(s.openUntil);
  }
  success(name) { this.state.set(name, { failures: 0, openUntil: 0 }); }
  failure(name) { const s = this.state.get(name) || { failures: 0, openUntil: 0 }; s.failures += 1; if (s.failures >= this.failureThreshold) s.openUntil = Date.now() + this.cooldownMs; this.state.set(name, s); }
  status() { return Object.fromEntries([...this.state].map(([k,v]) => [k, {...v, open: Boolean(v.openUntil && v.openUntil > Date.now())}])); }
}

export function tokenize(text = "") { return String(text).toLowerCase().replace(/&/g," and ").replace(/[@]/g," at ").replace(/\b(vs?|versus)\b/g," ").replace(/[^a-z0-9]+/g," ").split(/\s+/).filter(Boolean); }
export function normalizeName(text = "") { return tokenize(text).join(" "); }
export function similarity(a = "", b = "") { const A=new Set(tokenize(a)), B=new Set(tokenize(b)); if(!A.size||!B.size)return 0; let common=0; for(const x of A)if(B.has(x))common++; return common/Math.max(A.size,B.size); }
export function eventKey(event) { const ids=[event?.home?.short,event?.away?.short].filter(Boolean).sort(); const t=event?.start?new Date(event.start).toISOString().slice(0,13):"unknown"; return `${normalizeName(event?.league||"")}:${ids.join("-")}:${t}`; }

function teamAliases(team = {}) {
  const full = normalizeName(team?.name || team?.displayName || "");
  const short = normalizeName(team?.short || team?.abbreviation || "");
  const tokens = full.split(" ").filter(Boolean);
  const nickname = tokens.length > 1 ? tokens[tokens.length - 1] : full;
  const aliases = [full, short, nickname].filter(x => x && x.length >= 3);
  return [...new Set(aliases)];
}

function containsPhrase(haystack, phrase) {
  if (!haystack || !phrase) return false;
  return ` ${haystack} `.includes(` ${phrase} `) || haystack.includes(phrase);
}

// Streamio/Sportio-style tiered matchup matching. Full team names and
// nicknames are preferred, league/context and kickoff time strengthen a
// match, and unrelated-looking channels are naturally kept below stronger
// candidates instead of being allowed to win on a single generic token.
export function matchScore(channel, event) {
  const nameText = normalizeName(channel?.name || "");
  const contextText = normalizeName(`${channel?.group || ""} ${channel?.id || ""}`);
  const hay = normalizeName(`${channel?.name || ""} ${channel?.group || ""} ${channel?.id || ""}`);
  const homeAliases = teamAliases(event?.home);
  const awayAliases = teamAliases(event?.away);
  const homeFull = homeAliases[0] || "";
  const awayFull = awayAliases[0] || "";
  const homeShort = homeAliases[1] || "";
  const awayShort = awayAliases[1] || "";
  const homeNameHit = homeFull && containsPhrase(nameText, homeFull);
  const awayNameHit = awayFull && containsPhrase(nameText, awayFull);
  const homeAliasHit = homeAliases.some(a => containsPhrase(nameText, a));
  const awayAliasHit = awayAliases.some(a => containsPhrase(nameText, a));
  const homeContextHit = homeAliases.some(a => containsPhrase(contextText, a));
  const awayContextHit = awayAliases.some(a => containsPhrase(contextText, a));
  const league = normalizeName(event?.league || event?.sport || "");
  let score = 0;

  // Tier 1: both teams confirmed directly in the channel name.
  if (homeNameHit && awayNameHit) score += 70;
  // Tier 2: both team identities confirmed in name/context, even when the
  // provider omits the full matchup title from the channel name.
  else if (homeAliasHit && awayAliasHit) score += 58;
  // Tier 3: one team in the name plus the other in provider context.
  else if ((homeAliasHit && awayContextHit) || (awayAliasHit && homeContextHit)) score += 46;
  // Tier 4: a single real team nickname is still useful, but deliberately
  // scores lower than a two-team confirmation.
  else if (homeAliasHit || awayAliasHit) score += 28;

  if (homeShort && containsPhrase(nameText, homeShort)) score += 12;
  if (awayShort && containsPhrase(nameText, awayShort)) score += 12;
  if (homeFull && containsPhrase(contextText, homeFull)) score += 8;
  if (awayFull && containsPhrase(contextText, awayFull)) score += 8;
  if (league && containsPhrase(hay, league)) score += 8;

  const titleSimilarity = similarity(channel?.name || "", event?.title || "");
  score += Math.round(titleSimilarity * 12);

  const channelTime = channel?.start || channel?.date || channel?.datetime;
  if (channelTime && event?.start) {
    const delta = Math.abs(new Date(channelTime).getTime() - new Date(event.start).getTime());
    if (Number.isFinite(delta)) {
      if (delta <= 15 * 60_000) score += 20;
      else if (delta <= 60 * 60_000) score += 10;
      else if (delta <= 3 * 60 * 60_000) score += 4;
    }
  }

  const qualityText = `${channel?.name || ""} ${channel?.group || ""}`.toLowerCase();
  if (/\b(4k|2160p|uhd)\b/.test(qualityText)) score += 5;

  return Math.min(100, score);
}

export function rankStreams(streams) { const quality=s=>{const x=`${s.name} ${s.description} ${s.url}`.toLowerCase(); if(x.includes("4k")||x.includes("2160"))return 40; if(x.includes("1080")||x.includes("fhd"))return 30; if(x.includes("720")||x.includes("hd"))return 20; return 10;}; return [...streams].sort((a,b)=>(b.score||0)-(a.score||0)||quality(b)-quality(a)||(b.priority||0)-(a.priority||0)); }
export async function fetchWithTimeout(url,options={},timeoutMs=9000){const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),timeoutMs);try{return await fetch(url,{redirect:"follow",...options,signal:controller.signal,headers:{"User-Agent":"XSportsX/4.3.3 Nuvio addon",...(options.headers||{})}});}finally{clearTimeout(timer);}}
export async function fetchText(url,options={},timeoutMs=9000){const r=await fetchWithTimeout(url,options,timeoutMs);if(!r.ok)throw new Error(`${r.status} ${r.statusText}`);return r.text();}
export async function fetchJson(url,options={},timeoutMs=9000){const r=await fetchWithTimeout(url,options,timeoutMs);if(!r.ok)throw new Error(`${r.status} ${r.statusText}`);return r.json();}
