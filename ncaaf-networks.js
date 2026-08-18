export const NCAAF_NETWORKS = [
  { id: "acc-network", name: "ACC Network", aliases: ["ACC Network", "ACCN"], conference: "ACC" },
  { id: "accnx", name: "ACCNX", aliases: ["ACCNX", "ACC Network Extra"], conference: "ACC" },
  { id: "sec-network", name: "SEC Network", aliases: ["SEC Network", "SECN"], conference: "SEC" },
  { id: "sec-network-plus", name: "SEC Network+", aliases: ["SEC Network+", "SECN+"] , conference: "SEC" },
  { id: "big-ten-network", name: "Big Ten Network", aliases: ["Big Ten Network", "BTN"], conference: "Big Ten" },
  { id: "espn", name: "ESPN", aliases: ["ESPN"] },
  { id: "espn2", name: "ESPN2", aliases: ["ESPN2"] },
  { id: "espnu", name: "ESPNU", aliases: ["ESPNU"] },
  { id: "espn-plus", name: "ESPN+", aliases: ["ESPN+", "ESPN Plus"] },
  { id: "abc", name: "ABC", aliases: ["ABC"] },
  { id: "fox", name: "FOX", aliases: ["FOX"] },
  { id: "fs1", name: "FS1", aliases: ["FS1"] },
  { id: "fs2", name: "FS2", aliases: ["FS2"] },
  { id: "nbc", name: "NBC", aliases: ["NBC"] },
  { id: "cbs", name: "CBS", aliases: ["CBS"] },
  { id: "cbs-sports-network", name: "CBS Sports Network", aliases: ["CBS Sports Network", "CBSSN"] },
  { id: "the-cw", name: "The CW", aliases: ["The CW", "CW"] }
];

const norm = value => String(value || "").toLowerCase().replace(/[^a-z0-9+]+/g, " ").trim();
export function networkMatches(event, network) {
  const broadcasts = Array.isArray(event?.broadcast) ? event.broadcast : [];
  const text = norm(broadcasts.join(" | "));
  return network.aliases.some(alias => text.includes(norm(alias)));
}

export function networkMeta(network, events, poster) {
  const matches = events.filter(e => networkMatches(e, network));
  const videos = matches.slice(0, 100).map(e => ({
    id: `sport:game-${e.eventId}`,
    title: `${e.state === "in" ? "🔴 LIVE • " : ""}${e.title}`,
    released: e.start,
    thumbnail: `${poster}/${encodeURIComponent(e.eventId)}.svg`,
    overview: `${network.name}${e.detail ? ` • ${e.detail}` : ""}${e.venue ? ` • ${e.venue}` : ""}`
  }));
  return {
    id: `sport:ncaaf-network-${network.id}`,
    type: "sport",
    name: `📺 ${network.name}`,
    poster: `/leagues/ncaaf.gif`,
    background: `/visuals/league/ncaaf.svg`,
    description: `${network.name}${network.conference ? ` • ${network.conference}` : ""}\n\n${matches.filter(e => e.state === "in").length} LIVE • ${matches.length} scheduled games`,
    genres: ["Sports", "NCAA Football", "Networks", network.name].filter(Boolean),
    videos,
    behaviorHints: { defaultVideoId: videos[0]?.id }
  };
}
