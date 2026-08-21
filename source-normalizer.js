// Normalize authorized source data discovered by the XSportsX scanner.
// This module detects common M3U, Xtream-style and Stalker/Portal configuration
// shapes without attempting to bypass authentication or discover credentials.

function clean(v) { return String(v ?? '').trim(); }

function isHttp(v) { return /^https?:\/\//i.test(clean(v)); }

function detectM3U(text) {
  const s = clean(text);
  if (!/^#EXTM3U\b/im.test(s) && !/^#EXTINF:/im.test(s)) return null;
  const entries = [];
  const lines = s.split(/\r?\n/).map(x => x.trim()).filter(Boolean);
  for (let i = 0; i < lines.length; i++) {
    if (!/^#EXTINF:/i.test(lines[i])) continue;
    const url = lines[i + 1] && isHttp(lines[i + 1]) ? lines[i + 1] : null;
    if (url) entries.push({ title: lines[i].replace(/^#EXTINF:[^,]*,?/i, '').trim(), url });
  }
  return { type: 'm3u', entryCount: entries.length, entries: entries.slice(0, 500) };
}

function detectXtream(text) {
  const s = clean(text);
  const candidates = [];
  const add = (server, username, password) => {
    server = clean(server).replace(/\/$/, ''); username = clean(username); password = clean(password);
    if (isHttp(server) && username && password) candidates.push({ type: 'xtream', server, username, password });
  };
  // Common URL form: /get.php?username=...&password=...&type=m3u
  for (const raw of s.match(/https?:\/\/[^\s"'<>]+/gi) || []) {
    try {
      const u = new URL(raw);
      const username = u.searchParams.get('username');
      const password = u.searchParams.get('password');
      if (username && password && /(get\.php|player_api\.php|xmltv\.php|panel_api)/i.test(u.pathname)) add(`${u.protocol}//${u.host}`, username, password);
    } catch {}
  }
  // JSON/object forms: server/url + username + password.
  const server = s.match(/(?:server|serverUrl|url|host)\s*["']?\s*[:=]\s*["'](https?:\/\/[^"']+)/i)?.[1];
  const username = s.match(/(?:username|user)\s*["']?\s*[:=]\s*["']([^"']+)/i)?.[1];
  const password = s.match(/(?:password|pass)\s*["']?\s*[:=]\s*["']([^"']+)/i)?.[1];
  if (server && username && password) add(server, username, password);
  return candidates.length ? { type: 'xtream', sources: candidates.slice(0, 20) } : null;
}

function detectStalker(text) {
  const s = clean(text);
  const portals = new Set();
  for (const raw of s.match(/https?:\/\/[^\s"'<>]+/gi) || []) {
    try {
      const u = new URL(raw);
      if (/\/stalker_portal\b|\/portal\.php\b|\/c\/|\/server\/load\.php\b/i.test(u.pathname)) portals.add(`${u.protocol}//${u.host}${u.pathname}`.replace(/\/+$/, ''));
    } catch {}
  }
  // Also recognize explicit portal fields in a user-supplied config.
  const explicit = s.match(/(?:portal|portalUrl|portal_url)\s*["']?\s*[:=]\s*["'](https?:\/\/[^"']+)/i)?.[1];
  if (explicit) portals.add(explicit.replace(/\/+$/, ''));
  return portals.size ? { type: 'stalker', portals: [...portals].slice(0, 20), requiresUserAuthorization: true } : null;
}

export function normalizeSourceText(text) {
  const s = clean(text);
  const formats = [];
  const m3u = detectM3U(s); if (m3u) formats.push(m3u);
  const xtream = detectXtream(s); if (xtream) formats.push(xtream);
  const stalker = detectStalker(s); if (stalker) formats.push(stalker);
  return { detected: formats.length > 0, formats };
}
