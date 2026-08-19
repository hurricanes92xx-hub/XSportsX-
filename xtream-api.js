import { buildM3U, buildXMLTV, pickPlayableStream } from "./nuvio-live-tv.js";

const USERNAME = process.env.XTREAM_USERNAME || "";
const PASSWORD = process.env.XTREAM_PASSWORD || "";
const BASE_URL = process.env.BASE_URL || "https://xsportsx.onrender.com";
const VERSION = "4.2.1";

function authOk(username, password) {
  return Boolean(USERNAME && PASSWORD && username === USERNAME && password === PASSWORD);
}

function unauthorized() {
  return { ok: false, status: 401, body: { user_info: { auth: 0, status: "Disabled" }, server_info: {} } };
}

function streamId(meta, index) {
  const raw = String(meta?.id || index + 1).replace(/[^a-zA-Z0-9]/g, "");
  let hash = 0;
  for (const ch of raw) hash = ((hash * 31) + ch.charCodeAt(0)) >>> 0;
  return String(100000 + (hash % 899999));
}

function categoryId(name) {
  let hash = 0;
  for (const ch of String(name)) hash = ((hash * 31) + ch.charCodeAt(0)) >>> 0;
  return String(1000 + (hash >>> 0) % 8999);
}

function categoryFor(meta) {
  const text = [meta?.name, meta?.description, ...(meta?.genres || [])].join(" ").toLowerCase();
  if (/ufc|mma|fight/.test(text)) return "UFC";
  if (/ncaa|college football|cfp|big ten|sec|acc|big 12/.test(text)) return "NCAA Football";
  if (/nfl|football/.test(text)) return "NFL";
  if (/nba|basketball/.test(text)) return "NBA";
  if (/nhl|hockey/.test(text)) return "NHL";
  if (/mlb|baseball/.test(text)) return "MLB";
  return "Sports";
}

export function xtreamConfigured() {
  return Boolean(USERNAME && PASSWORD);
}

export function xtreamAuth(reqUrl) {
  const u = new URL(reqUrl, BASE_URL);
  return { username: u.searchParams.get("username") || "", password: u.searchParams.get("password") || "" };
}

export function xtreamCredentialsMatch(username, password) {
  return authOk(username, password);
}

export function xtreamUserInfo() {
  const now = Math.floor(Date.now() / 1000);
  return {
    username: USERNAME,
    password: PASSWORD,
    message: "XSportsX Sports EPG",
    auth: 1,
    status: "Active",
    exp_date: "0",
    is_trial: "0",
    active_cons: "0",
    created_at: String(now),
    max_connections: "99",
    allowed_output_formats: ["ts", "m3u8"]
  };
}

export function xtreamServerInfo() {
  const base = new URL(BASE_URL);
  return {
    url: base.hostname,
    port: base.port || (base.protocol === "https:" ? "443" : "80"),
    https_port: base.protocol === "https:" ? (base.port || "443") : "443",
    server_protocol: base.protocol.replace(":", ""),
    timezone: "UTC",
    timestamp_now: Math.floor(Date.now() / 1000),
    time_now: new Date().toISOString().replace("T", " ").replace(/\.\d{3}Z$/, ""),
    process: true
  };
}

export function xtreamCategories(metas) {
  const names = [...new Set((metas || []).map(categoryFor))].sort();
  return names.map(name => ({ category_id: categoryId(name), category_name: name, parent_id: 0 }));
}

export function xtreamStreams(metas) {
  return (metas || []).map((meta, index) => {
    const id = streamId(meta, index);
    const category = categoryFor(meta);
    const icon = meta.logo || meta.poster || meta.background || "";
    return {
      num: index + 1,
      name: String(meta.name || "Sports Event"),
      stream_type: "live",
      stream_id: Number(id),
      stream_icon: icon,
      epg_channel_id: String(meta.id),
      added: String(Math.floor(Date.now() / 1000)),
      category_id: categoryId(category),
      tv_archive: 0,
      direct_source: `${BASE_URL}/live/${encodeURIComponent(USERNAME)}/${encodeURIComponent(PASSWORD)}/${id}.m3u8`,
      container_extension: "m3u8"
    };
  });
}

export function xtreamIdMap(metas) {
  const map = new Map();
  (metas || []).forEach((meta, index) => map.set(streamId(meta, index), meta));
  return map;
}

export function xtreamM3U(metas, output = "ts") {
  const rows = [`#EXTM3U x-tvg-url="${BASE_URL}/xmltv.php?username=${encodeURIComponent(USERNAME)}&password=${encodeURIComponent(PASSWORD)}"`];
  for (const [index, meta] of (metas || []).entries()) {
    const id = streamId(meta, index);
    const category = categoryFor(meta);
    const logo = meta.logo || meta.poster || meta.background || "";
    rows.push(`#EXTINF:-1 tvg-id="${String(meta.id).replace(/"/g, "&quot;")}" tvg-name="${String(meta.name || "Sports Event").replace(/"/g, "&quot;")}" tvg-logo="${logo}" group-title="${category}",${String(meta.name || "Sports Event")}`);
    rows.push(`${BASE_URL}/live/${encodeURIComponent(USERNAME)}/${encodeURIComponent(PASSWORD)}/${id}.${output === "m3u8" ? "m3u8" : "ts"}`);
  }
  return `${rows.join("\n")}\n`;
}

export function xtreamXMLTV(metas) {
  return buildXMLTV(metas);
}

export function xtreamAccountResponse() {
  return { user_info: xtreamUserInfo(), server_info: xtreamServerInfo() };
}

export function xtreamUnauthorizedResponse() {
  return unauthorized();
}

export function xtreamPlayUrl(meta) {
  return `${BASE_URL}/play/${encodeURIComponent(String(meta?.id || ""))}`;
}

export async function resolveXtreamStream(meta, gateway) {
  const payload = await gateway(`/stream/sport/${encodeURIComponent(String(meta?.id || ""))}.json`);
  return pickPlayableStream(payload);
}
