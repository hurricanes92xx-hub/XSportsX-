const NETWORKS = [
  ['ESPN', 'espn'], ['ESPN News', 'espnnews'], ['ESPN Deportes', 'espndeportes'],
  ['FOX Sports', 'fox sports'], ['FS1', 'fs1'], ['FS2', 'fs2'],
  ['NBC Sports', 'nbc sports'], ['CBS Sports', 'cbs sports'],
  ['TNT Sports', 'tnt sports'], ['TBS Sports', 'tbs sports'],
  ['NFL Network', 'nfl network'], ['MLB Network', 'mlb network'],
  ['NHL Network', 'nhl network'], ['NBA TV', 'nba tv'],
  ['UFC', 'ufc'], ['Fight Pass', 'ufc fight pass'],
  ['F1', 'formula 1'], ['NASCAR', 'nascar'], ['PGA', 'pga tour'],
  ['FIFA', 'fifa'], ['UEFA', 'uefa'], ['YouTube Sports', 'youtube sports']
];

const OFFICIALS = [
  ['ESPN', 'https://www.espn.com/watch/'],
  ['FOX Sports', 'https://www.foxsports.com/live'],
  ['FOX One', 'https://www.fox.com/sports'],
  ['UFC', 'https://www.ufc.com/watch'],
  ['FIFA+', 'https://www.plus.fifa.com/'],
  ['Red Bull TV', 'https://www.redbull.com/us-en/live']
];

const EVENT_WORDS = /\b(nfl|nba|nhl|mlb|ufc|mma|boxing|wwe|nascar|f1|formula 1|pga|golf|soccer|football|tennis|cricket|rugby|fifa|uefa)\b/i;

function clean(v) { return String(v || '').trim(); }
function terms(event = {}) {
  return [event.home, event.away, event.name, event.league, event.sport].map(clean).filter(Boolean).join(' ');
}

export function coverageQueries(event = {}) {
  const t = terms(event) || 'live sports';
  return NETWORKS.flatMap(([name, q]) => [
    `${t} ${q} live official`,
    `${t} ${q} where to watch`,
    `${t} ${q} live stream official`,
    `${t} ${q} schedule`
  ]);
}

export function officialCoverage(event = {}) {
  const t = terms(event);
  const out = OFFICIALS.filter(([name]) => !t || EVENT_WORDS.test(t) || /ESPN|FOX|UFC|FIFA|Red Bull/.test(name))
    .map(([name, url]) => ({ name, url, type: 'official-coverage', event: t }));
  return out;
}

export function mergeCoverage(event = {}, webResults = [], playableSources = []) {
  const seen = new Set();
  const out = [];
  for (const item of [...playableSources, ...webResults, ...officialCoverage(event)]) {
    if (!item?.url || seen.has(item.url)) continue;
    seen.add(item.url);
    out.push({ ...item, event: item.event || terms(event), playable: Boolean(item.playable ?? item.ok) });
  }
  return out.sort((a, b) => Number(b.playable) - Number(a.playable) || (a.latencyMs || 99999) - (b.latencyMs || 99999));
}

export { NETWORKS };
