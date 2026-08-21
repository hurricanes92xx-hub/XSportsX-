import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const defaultFile = fs.existsSync('/var/data') ? '/var/data/xsportsx-source-state.json' : path.join(process.cwd(), 'data', 'xsportsx-source-state.json');
const file = process.env.SOURCE_STATE_FILE || defaultFile;
const mem = new Map();
const STATE_VERSION = 3;

function keyFor(config) { return crypto.createHash('sha256').update(String(config || '')).digest('hex'); }
function empty() { return { version: STATE_VERSION, updatedAt: null, sourceUrls: [], pending: [], approved: [], rejected: [], diagnostics: {} }; }
function loadAll() { try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return {}; } }
function saveAll(all) { fs.mkdirSync(path.dirname(file), { recursive: true }); const tmp = `${file}.tmp`; fs.writeFileSync(tmp, JSON.stringify(all), 'utf8'); fs.renameSync(tmp, file); }

export function getSourceState(config) {
  const key = keyFor(config);
  if (mem.has(key)) return mem.get(key);
  const all = loadAll();
  const raw = all[key] || empty();
  const state = {
    version: STATE_VERSION,
    updatedAt: raw.updatedAt || null,
    sourceUrls: Array.isArray(raw.sourceUrls) ? [...new Set(raw.sourceUrls.map(String))].slice(0, 25) : [],
    pending: Array.isArray(raw.pending) ? raw.pending : [],
    approved: Array.isArray(raw.approved) ? raw.approved : [],
    rejected: Array.isArray(raw.rejected) ? raw.rejected : [],
    diagnostics: raw.diagnostics && typeof raw.diagnostics === 'object' ? raw.diagnostics : {}
  };
  mem.set(key, state);
  return state;
}

export function setSourceState(config, state) {
  const key = keyFor(config);
  const clean = {
    version: STATE_VERSION,
    updatedAt: new Date().toISOString(),
    sourceUrls: Array.isArray(state.sourceUrls) ? [...new Set(state.sourceUrls.map(String))].slice(0, 25) : [],
    pending: Array.isArray(state.pending) ? state.pending.slice(0, 500) : [],
    approved: Array.isArray(state.approved) ? state.approved.slice(0, 500) : [],
    rejected: Array.isArray(state.rejected) ? state.rejected.slice(-1000) : [],
    diagnostics: state.diagnostics && typeof state.diagnostics === 'object' ? state.diagnostics : {}
  };
  mem.set(key, clean);
  const all = loadAll();
  all[key] = clean;
  saveAll(all);
  return clean;
}
