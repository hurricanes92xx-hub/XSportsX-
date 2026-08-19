const XMLTV_TZ = "+0000";

function xml(value = "") {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function safeId(value) {
  return encodeURIComponent(String(value || "sport:event"));
}

function startTime(meta) {
  const raw = meta?.released || meta?.releaseInfo || meta?.date;
  const parsed = raw ? Date.parse(raw) : NaN;
  return Number.isFinite(parsed) ? new Date(parsed) : new Date();
}

function stamp(date) {
  const d = new Date(date);
  const iso = new Date(d.getTime() + d.getTimezoneOffset() * 60000).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "");
  return `${iso}${XMLTV_TZ}`;
}

function networkFor(meta) {
  const text = [meta?.name, meta?.description, ...(meta?.genres || [])].join(" ").toLowerCase();
  const rules = [
    ["ESPN2", ["espn2"]], ["ESPNU", ["espnu"]], ["ESPN", ["espn"]],
    ["NFL Network", ["nfl network"]], ["NHL Network", ["nhl network"]],
    ["MLB Network", ["mlb network"]], ["NBA TV", ["nba tv"]],
    ["ACC Network", ["acc network", "accn"]], ["Big Ten Network", ["big ten network", "btn"]],
    ["SEC Network", ["sec network", "secn"]], ["Big 12 Now", ["big 12 now", "big12 now"]],
    ["FOX Sports 1", ["fox sports 1", "fs1"]], ["FOX Sports 2", ["fox sports 2", "fs2"]],
    ["CBS Sports Network", ["cbs sports network", "cbssn"]], ["ABC", ["abc"]],
    ["CBS", ["cbs"]], ["FOX", ["fox"]], ["NBC", ["nbc"]]
  ];
  return rules.find(([, aliases]) => aliases.some(alias => text.includes(alias)))?.[0] || "Sports";
}

export function buildM3U(metas, baseUrl) {
  const rows = ["#EXTM3U x-tvg-url=\"${baseUrl}/epg.xml\""];
  for (const meta of metas || []) {
    if (!meta?.id || !meta?.name) continue;
    const id = String(meta.id);
    const network = networkFor(meta);
    const logo = meta.logo || meta.poster || meta.background || "";
    const name = String(meta.name).replace(/\s+/g, " ").trim();
    const group = `Sports / ${network}`;
    rows.push(`#EXTINF:-1 tvg-id="${id.replace(/"/g, "&quot;")}" tvg-name="${name.replace(/"/g, "&quot;")}" tvg-logo="${logo}" group-title="${group}",${name}`);
    rows.push(`${baseUrl}/play/${safeId(id)}`);
  }
  return `${rows.join("\n")}\n`;
}

export function buildXMLTV(metas) {
  const channels = [];
  const programmes = [];
  for (const meta of metas || []) {
    if (!meta?.id || !meta?.name) continue;
    const id = String(meta.id);
    const network = networkFor(meta);
    const logo = meta.logo || meta.poster || meta.background || "";
    const start = startTime(meta);
    const stop = new Date(start.getTime() + 3 * 60 * 60 * 1000);
    channels.push(`  <channel id="${xml(id)}"><display-name>${xml(`${network} • ${meta.name}`)}</display-name>${logo ? `<icon src="${xml(logo)}"/>` : ""}</channel>`);
    programmes.push(`  <programme start="${stamp(start)}" stop="${stamp(stop)}" channel="${xml(id)}"><title>${xml(meta.name)}</title><sub-title>${xml(network)}</sub-title><desc>${xml(meta.description || "Live sports event")}</desc>${logo ? `<icon src="${xml(logo)}"/>` : ""}</programme>`);
  }
  return `<?xml version="1.0" encoding="UTF-8"?>\n<tv generator-info-name="XSportsX Sports EPG" generator-info-url="https://xsportsx.onrender.com">\n${channels.join("\n")}\n${programmes.join("\n")}\n</tv>\n`;
}

export function pickPlayableStream(payload) {
  const streams = Array.isArray(payload?.streams) ? payload.streams : [];
  return streams.find(stream => typeof stream?.url === "string" && /^https?:\/\//i.test(stream.url))
    || streams.find(stream => typeof stream?.streamUrl === "string" && /^https?:\/\//i.test(stream.streamUrl))
    || null;
}
