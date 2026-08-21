import fs from 'node:fs/promises';
import { Buffer } from 'node:buffer';

const DEFAULT_MIN_SOURCES = 5;
const DEFAULT_TIMEOUT_MS = 7000;
const URL_RE = /https?:\/\/[^\s"'<>]+/gi;

export function decodeBase64(value) {
  const cleaned = String(value ?? '')
    .replace(/\s+/g, '')
    .replace(/-/g, '+')
    .replace(/_/g, '/');
  if (!cleaned || !/^[A-Za-z0-9+/]*={0,2}$/.test(cleaned)) return null;
  try {
    const padded = cleaned.padEnd(Math.ceil(cleaned.length / 4) * 4, '=');
    const decoded = Buffer.from(padded, 'base64').toString('utf8').trim();
    return decoded || null;
  } catch {
    return null;
  }
}

export function extractUrls(text) {
  return [...new Set(String(text ?? '').match(URL_RE) ?? [])]
    .map((u) => u.replace(/[),.;]+$/, ''));
}

export function decodeBase64Urls(text) {
  const out = new Set(extractUrls(text));
  for (const token of String(text ?? '').split(/\s+/)) {
    const decoded = decodeBase64(token);
    if (decoded) for (const url of extractUrls(decoded)) out.add(url);
  }
  return [...out];
}

async function fetchWithTimeout(url, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, {
      method: 'GET',
      redirect: 'follow',
      signal: controller.signal,
      headers: { 'user-agent': 'XSportsX-source-health/1.0' },
    });
  } finally {
    clearTimeout(timer);
  }
}

export async function healthCheck(url, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const started = Date.now();
  try {
    const response = await fetchWithTimeout(url, timeoutMs);
    const contentType = response.headers.get('content-type') || '';
    return {
      url,
      ok: response.ok,
      status: response.status,
      latencyMs: Date.now() - started,
      contentType,
      checkedAt: new Date().toISOString(),
    };
  } catch (error) {
    return {
      url,
      ok: false,
      status: 0,
      latencyMs: Date.now() - started,
      error: error?.name === 'AbortError' ? 'timeout' : String(error?.message || error),
      checkedAt: new Date().toISOString(),
    };
  }
}

function uniqueSources(sources) {
  const seen = new Set();
  return sources.filter((source) => {
    const url = source?.url;
    if (!url || seen.has(url)) return false;
    seen.add(url);
    return true;
  });
}

export async function maintainSources({
  candidates = [],
  existing = [],
  minSources = DEFAULT_MIN_SOURCES,
  timeoutMs = DEFAULT_TIMEOUT_MS,
} = {}) {
  const pool = uniqueSources([...existing, ...candidates]);
  const checks = await Promise.all(pool.map((source) => healthCheck(source.url, timeoutMs)));
  const healthy = checks
    .filter((result) => result.ok)
    .sort((a, b) => a.latencyMs - b.latencyMs)
    .map((result) => pool.find((source) => source.url === result.url));

  return {
    active: healthy.slice(0, Math.max(minSources, healthy.length)),
    checks,
    healthyCount: healthy.length,
    minimumMet: healthy.length >= minSources,
  };
}

export async function loadAuthorizedSourceFeed(feedUrls = []) {
  const all = [];
  for (const feedUrl of feedUrls) {
    const response = await fetchWithTimeout(feedUrl, DEFAULT_TIMEOUT_MS);
    if (!response.ok) continue;
    const body = await response.text();
    for (const url of decodeBase64Urls(body)) all.push({ url, feedUrl });
  }
  return uniqueSources(all);
}

export async function loadSourceState(path = './sources.json') {
  try {
    return JSON.parse(await fs.readFile(path, 'utf8'));
  } catch {
    return { minSources: DEFAULT_MIN_SOURCES, sources: [] };
  }
}

export async function saveSourceState(state, path = './sources.json') {
  await fs.writeFile(path, JSON.stringify(state, null, 2) + '\n', 'utf8');
}

export async function refreshAuthorizedSources({
  statePath = './sources.json',
  feedUrls = String(process.env.AUTHORIZED_SOURCE_FEEDS || '')
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean),
  minSources = Number(process.env.MIN_SOURCES || DEFAULT_MIN_SOURCES),
} = {}) {
  const state = await loadSourceState(statePath);
  const candidates = await loadAuthorizedSourceFeed(feedUrls);
  const result = await maintainSources({
    candidates,
    existing: state.sources || [],
    minSources,
  });

  const next = {
    minSources,
    updatedAt: new Date().toISOString(),
    sources: result.active,
    lastChecks: result.checks,
    minimumMet: result.minimumMet,
  };
  await saveSourceState(next, statePath);
  return next;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const state = await refreshAuthorizedSources();
  console.log(JSON.stringify(state, null, 2));
  if (!state.minimumMet) process.exitCode = 2;
}
