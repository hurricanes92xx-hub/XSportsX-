import { fetchWithTimeout, matchScore, rankStreams } from "./core.js";

const cache = new Map();
const sessions = new Map();
const breakers = new Map();

function now() { return Date.now(); }
function sourceKey(src) { return String(src?.name || src?.portal || "stalker"); }
function portalBase(src) { return String(src?.portal || "").replace(/\/+$/, ""); }
function loadUrl(src, params) {
  const endpoint = src?.loadPath || "/stalker_portal/server/load.php";
  const url = new URL(endpoint, `${portalBase(src)}/`);
  for (const [key, value] of Object.entries(params)) if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
  return url.toString();
}
function headers(src, token, cookie) {
  const mac = String(src?.mac || "").trim();
  return {
    Accept: "*/*",
    "X-User-Agent": src?.userAgent || "Model: MAG254; Link: Ethernet",
    ...(mac ? { Cookie: `mac=${encodeURIComponent(mac)};${cookie ? ` ${cookie}` : ""}` } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(src?.headers || {})
  };
}
function openBreaker(key) { const state = breakers.get(key); return Boolean(state?.openUntil && state.openUntil > now()); }
function fail(key) { const state = breakers.get(key) || { failures: 0, openUntil: 0 }; state.failures += 1; if (state.failures >= 3) state.openUntil = now() + 60_000; breakers.set(key, state); }
function success(key) { breakers.set(key, { failures: 0, openUntil: 0 }); }

async function request(src, params, token, cookie, timeout) {
  const response = await fetchWithTimeout(loadUrl(src, params), { headers: headers(src, token, cookie) }, timeout);
  const setCookie = response.headers.get("set-cookie") || cookie || "";
  if (!response.ok) throw new Error(`stalker:${response.status}`);
  return { data: await response.json(), cookie: setCookie };
}

async function getSession(src, timeout) {
  const key = sourceKey(src);
  const cached = sessions.get(key);
  if (cached && cached.expires > now()) return cached;
  const handshake = await request(src, { type: "stb", action: "handshake", token: "" }, "", src.cookie || "", timeout);
  const token = handshake.data?.js?.token || handshake.data?.token || "";
  const cookie = handshake.cookie || src.cookie || "";
  if (!token && src.requireToken !== false) throw new Error("stalker:handshake-token");
  const session = { token, cookie, expires: now() + Number(src.sessionTtlMs || 300_000) };
  sessions.set(key, session);
  return session;
}

async function getChannels(src, timeout) {
  const key = `stalker:${sourceKey(src)}`;
  const cached = cache.get(key);
  if (cached && cached.expires > now()) return { channels: cached.value, session: cached.session };
  if (openBreaker(key)) return { channels: cached?.value || [], session: cached?.session || null };
  try {
    const session = await getSession(src, timeout);
    await request(src, { type: "stb", action: "get_profile", auth_second: session.token }, session.token, session.cookie, timeout).catch(() => null);
    const pageSize = Math.min(1000, Number(src.pageSize || 500));
    const response = await request(src, {
      type: "itv", action: "get_all_channels", p: 1, js: 0, fav: 0, sortby: "number",
      force_ch_link_check: 0, hd: 0, g_type: 0, page: 1, page_size: pageSize, auth_second: session.token
    }, session.token, session.cookie, timeout);
    const channels = (Array.isArray(response.data?.js) ? response.data.js : []).map(channel => ({
      id: channel.id || channel.tv_genre_id || "",
      name: channel.name || "",
      group: channel.tv_genre_name || channel.tv_genre_id || "",
      logo: channel.logo || channel.cmd_icon || "",
      cmd: channel.cmd || channel.url || "",
      number: channel.number || "",
      start: channel.start || channel.tvg_start || "",
      raw: channel
    })).filter(x => x.cmd && x.name);
    success(key);
    cache.set(key, { value: channels, session, expires: now() + Number(src.cacheTtlMs || 300_000) });
    return { channels, session };
  } catch {
    fail(key);
    return { channels: cached?.value || [], session: cached?.session || null };
  }
}

async function createLink(src, channel, session, timeout) {
  const cmd = String(channel?.cmd || "");
  if (!cmd) return null;
  if (/^https?:\/\//i.test(cmd)) return cmd;
  const response = await request(src, {
    type: "itv", action: "create_link", cmd, series: 0, forced_storage: 0,
    disable_ad: 0, download: 0, force_ch_link_check: 0, JsHttpRequest: "1-xml", auth_second: session?.token || ""
  }, session?.token || "", session?.cookie || "", timeout);
  const link = response.data?.js?.cmd || response.data?.js?.url || response.data?.cmd || response.data?.url || "";
  const cleaned = String(link).replace(/^ffmpeg\s+/i, "").trim();
  return /^https?:\/\//i.test(cleaned) ? cleaned : null;
}

export async function stalkerStreamsForEvent(event, sources, timeout = 9000) {
  const out = [];
  for (const src of sources || []) {
    if (!src?.portal || !src?.mac) continue;
    const key = `stalker:${sourceKey(src)}`;
    if (openBreaker(key)) continue;
    try {
      const { channels, session } = await getChannels(src, timeout);
      const matches = channels.map(channel => ({ channel, score: matchScore(channel, event) }))
        .filter(x => x.score >= Number(src.minScore || 35)).sort((a, b) => b.score - a.score).slice(0, Number(src.maxMatches || 8));
      for (const match of matches) {
        const streamUrl = await createLink(src, match.channel, session, timeout).catch(() => null);
        if (!streamUrl) continue;
        out.push({
          name: `${src.name || "Authorized Stalker"} • ${match.channel.name}`,
          url: streamUrl,
          description: `${match.channel.group || "Stalker"} • match ${match.score}%`,
          logo: match.channel.logo || undefined,
          score: match.score, priority: Number(src.priority || 0), source: src.name || "stalker", protocol: "stalker"
        });
      }
      if (out.some(x => x.source === (src.name || "stalker"))) success(key);
    } catch { fail(key); }
  }
  return rankStreams(out);
}

export function stalkerStatus(sources = []) {
  return sources.map(src => ({ name: src?.name || src?.portal || "stalker", portal: src?.portal || "", configured: Boolean(src?.portal && src?.mac), circuit: breakers.get(`stalker:${sourceKey(src)}`) || { failures: 0, openUntil: 0 } }));
}
