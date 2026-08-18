import { fetchJson, normalizeName, similarity } from "./core.js";

// ESPN college-football rankings are the source of truth for NCAA ranking metadata.
const RANKINGS_URL = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/rankings";
const cache = { value: null, expires: 0, fetchedAt: 0, promise: null };
const TTL = 60 * 60_000;

function teamNames(team = {}) {
  return [team.name, team.shortName, team.abbreviation, team.displayName, team.location].filter(Boolean).map(normalizeName);
}

function parseRankings(data) {
  const out = [];
  for (const group of data?.rankings || []) {
    for (const entry of group?.ranks || []) {
      const team = entry?.team || {};
      const rank = Number(entry?.current ?? entry?.rank);
      if (!Number.isFinite(rank)) continue;
      out.push({
        rank,
        previousRank: Number(entry?.previous) || null,
        points: Number(entry?.points) || null,
        firstPlaceVotes: Number(entry?.firstPlaceVotes) || null,
        names: teamNames(team),
        name: team.displayName || team.name || team.shortName || "",
        abbreviation: team.abbreviation || ""
      });
    }
  }
  return out.sort((a,b) => a.rank - b.rank);
}

export async function getCollegeRankings() {
  if (cache.value && cache.expires > Date.now()) return cache.value;
  if (cache.promise) return cache.promise;
  cache.promise = (async () => {
    try {
      const data = await fetchJson(RANKINGS_URL, {}, 8000);
      const value = parseRankings(data);
      if (value.length) {
        cache.value = value;
        cache.expires = Date.now() + TTL;
        cache.fetchedAt = Date.now();
      } else if (cache.value) {
        cache.expires = Date.now() + 5 * 60_000;
      }
      return cache.value || value;
    } finally {
      cache.promise = null;
    }
  })();
  try { return await cache.promise; }
  catch { return cache.value || []; }
}

function matchTeam(eventTeam, rankings) {
  const names = teamNames(eventTeam);
  if (!names.length) return null;
  let best = null;
  for (const r of rankings) {
    let score = 0;
    for (const a of names) for (const b of r.names) {
      if (a === b) score = Math.max(score, 1);
      else if (a.includes(b) || b.includes(a)) score = Math.max(score, 0.9);
      else score = Math.max(score, similarity(a,b));
    }
    if (!best || score > best.score) best = { ranking:r, score };
  }
  return best && best.score >= 0.65 ? best.ranking : null;
}

export async function enrichNcaafEvents(events) {
  const rankings = await getCollegeRankings();
  return events.map(event => {
    if (String(event?.sport || "").toLowerCase() !== "ncaaf") return event;
    const home = matchTeam(event.home, rankings);
    const away = matchTeam(event.away, rankings);
    const ranked = [home, away].filter(Boolean);
    return {
      ...event,
      ranking: {
        source: "ESPN",
        home,
        away,
        ranked: ranked.length,
        rankedMatchup: Boolean(home && away),
        rankingsUpdatedAt: cache.fetchedAt || null
      }
    };
  });
}

export function cfpWatchEvents(events) {
  return events.filter(e => String(e?.sport || "").toLowerCase() === "ncaaf" && (e?.ranking?.rankedMatchup || e?.ranking?.ranked > 0));
}

export function cfpWatchMeta(event, gamePoster, gameOverview, scoreText, videoFor) {
  const r = event.ranking || {};
  const h = r.home ? `#${r.home.rank} ${r.home.name}` : (event.home?.short || event.home?.name || "Home");
  const a = r.away ? `#${r.away.rank} ${r.away.name}` : (event.away?.short || event.away?.name || "Away");
  const badge = r.rankedMatchup ? "🏆 CFP WATCH • RANKED MATCHUP" : "🏆 CFP WATCH";
  const movement = [r.home?.previousRank ? `#${r.home.previousRank}→#${r.home.rank}` : null, r.away?.previousRank ? `#${r.away.previousRank}→#${r.away.rank}` : null].filter(Boolean).join(" • ");
  const video = videoFor(event);
  video.title = `▶ WATCH • ${a} at ${h}${scoreText(event)}`;
  video.overview = `${badge}${movement ? ` • ${movement}` : ""} • ${gameOverview(event)}`;
  return {
    id:`sport:cfp-${event.eventId}`,
    type:"sport",
    name:`${badge} • ${a} at ${h}`,
    poster:gamePoster(event.eventId),
    background:gamePoster(event.eventId),
    description:`${event.state === "in" ? "🔴 LIVE • " : ""}${movement ? `${movement} • ` : ""}${gameOverview(event)}${scoreText(event)}`,
    genres:["Sports","NCAA Football","CFP Watch",event.league].filter(Boolean),
    releaseInfo:event.start ? new Date(event.start).toLocaleString() : "",
    videos:[video],
    behaviorHints:{defaultVideoId:video.id}
  };
}
