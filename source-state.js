import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const file = process.env.SOURCE_STATE_FILE || path.join(process.cwd(), 'data', 'xsportsx-source-state.json');
const mem = new Map();

function keyFor(config) {
  return crypto.createHash('sha256').update(String(config || '')).digest('hex');
}

function empty() { return { pending: [], approved: [] }; }

function loadAll() {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return {}; }
}

function saveAll(all) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(all), 'utf8');
  fs.renameSync(tmp, file);
}

export function getSourceState(config) {
  const key = keyFor(config);
  if (mem.has(key)) return mem.get(key);
  const all = loadAll();
  const state = all[key] || empty();
  mem.set(key, state);
  return state;
}

export function setSourceState(config, state) {
  const key = keyFor(config);
  const clean = {
    pending: Array.isArray(state.pending) ? state.pending.slice(0, 500) : [],
    approved: Array.isArray(state.approved) ? state.approved.slice(0, 500) : []
  };
  mem.set(key, clean);
  const all = loadAll();
  all[key] = clean;
  saveAll(all);
  return clean;
}

export function mutateSourceState(config, action, item, index) {
  const state = getSourceState(config);
  if (action === 'approve' && Number.isInteger(index) && state.pending[index]) state.approved.push(state.pending.splice(index, 1)[0]);
  else if (action === 'reject' && Number.isInteger(index) && state.pending[index]) state.pending.splice(index, 1);
  else if (action === 'revoke' && Number.isInteger(index) && state.approved[index]) state.approved.splice(index, 1);
  else if (action === 'add-pending' && item?.url) state.pending.push({ url: String(item.url), type: String(item.type || 'source'), healthy: !!item.healthy, details: String(item.details || '') });
  else if (action === 'add-approved' && item?.url) state.approved.push({ url: String(item.url), type: String(item.type || 'source'), healthy: !!item.healthy, details: String(item.details || '') });
  return setSourceState(config, state);
}
