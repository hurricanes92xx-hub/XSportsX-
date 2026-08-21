import * as coreProviders from "./providers-core.js";
import { stalkerStreamsForEvent, stalkerStatus } from "./stalker.js";
import { freeOfficialLinksForEvent, freeSourceStatus } from "./free-sources.js";

let rankingCache = null;
let rankingCacheAt = 0;
const RANKING_TTL_MS = 6 * 60 * 60 * 1000;
const stalkerSources = readJson("AUTHORIZED_STALKER_SOURCES", []);

function readJson(key, fallback) { try { return JSON.parse(process.env[key] || JSON.stringify(fallback)); } catch { return fallback; } }
function normalizeTeamName(value = "") {
  return String(value).toLowerCase().replace(/\b(the|university|of)\b/g, " ").replace(/[^a-z0-9]+/g, " ").replace(/\s+/g, " ").trim();
}

async function getNcaafRankings() {
  if (rankingCache && Date.now() - rankingCacheAt < RANKING_TTL_MS) return rankingCache;
  try {
    const response = await fetch("https://site.api.espn.com/apis/site/v2/sports/football/college-football/rankings?seasontype=2&type=0&level=3", { headers: { accept: "application/json" } });
    if (!response.ok) throw new Error(`rankings:${response.status}`);
    const data = await response.json();
    const poll = Array.isArray(data?.rankings) ? data.rankings[0] : null;
    const entries = Array.isArray(poll?.ranks) ? poll.ranks : [];
    const map = new Map();
    for (const entry of entries) {
      const team = entry?.team || {};
      const name = team?.displayName || team?.name || entry?.teamName || "";
      if (!name) continue;
      const rank = Number(entry?.current ?? entry?.rank ?? entry?.ranking);
      if (!Number.isFinite(rank)) continue;
      const info = { rank, name, abbreviation: team?.abbreviation || "", record: entry?.recordSummary || entry?.record || "", points: entry?.points ?? null, firstPlaceVotes: entry?.firstPlaceVotes ?? entry?.firstPlaceVotesReceived ?? 0, previousRank: entry?.previous ?? null, movement: entry?.trend || entry?.movement || "" };
      map.set(normalizeTeamName(name), info);
      if (team?.abbreviation) map.set(normalizeTeamName(team.abbreviation), info);
    }
    rankingCache = map;
    rankingCacheAt = Date.now();
    return map;
  } catch { return rankingCache || new Map(); }
}

function findRanking(team, rankings) {
  const candidates = [team?.name, team?.displayName, team?.short, team?.abbreviation].filter(Boolean).map(normalizeTeamName);
  for (const candidate of candidates) if (rankings.has(candidate)) return rankings.get(candidate);
  for (const candidate of candidates) {
    if (candidate.length < 5) continue;
    for (const [key, value] of rankings) if (key.includes(candidate) || candidate.includes(key)) return value;
  }
  return null;
}
function enrichNcaafEvent(event, rankings) {
  if (event?.sport !== "ncaaf") return event;
  const homeRank = findRanking(event.home, rankings), awayRank = findRanking(event.away, rankings);
  if (!homeRank && !awayRank) return event;
  return { ...event, home: homeRank ? { ...event.home, ranking: homeRank.rank, rankingInfo: homeRank } : event.home, away: awayRank ? { ...event.away, ranking: awayRank.rank, rankingInfo: awayRank } : event.away, rankings: [awayRank, homeRank].filter(Boolean).map(x => `#${x.rank} ${x.name}`).join(" vs ") };
}

export async function getEvents(options) {
  const events = await coreProviders.getEvents(options);
  const ncaaf = events.filter(event => event?.sport === "ncaaf");
  if (!ncaaf.length) return events;
  const rankings = await getNcaafRankings();
  if (!rankings.size) return events;
  return events.map(event => enrichNcaafEvent(event, rankings));
}

export const parseM3U = coreProviders.parseM3U;
export const newsStreamsForChannel = coreProviders.newsStreamsForChannel;

export async function streamsFor(event) {
  const key = `free-wrapper:${event.eventId}`;
  const [iptvStreams, stalkerStreams, freeLinks] = await Promise.all([
    coreProviders.streamsFor(event),
    stalkerStreamsForEvent(event, stalkerSources, Number(process.env.REQUEST_TIMEOUT_MS || 9000)),
    freeOfficialLinksForEvent(event)
  ]);
  const seen = new Set();
  const combined = [];
  for (const item of [...iptvStreams, ...stalkerStreams, ...freeLinks]) {
    const identity = item.url || item.externalUrl || `${item.name}:${item.description}`;
    if (seen.has(identity)) continue;
    seen.add(identity);
    combined.push(item);
  }
  return combined;
}

export function providerStatus() {
  return {
    ...coreProviders.providerStatus(),
    stalkerSources: stalkerStatus(stalkerSources),
    freeOfficialSources: freeSourceStatus()
  };
}
