const express = require('express');
const { URL } = require('url');

const originalUse = express.application.use;
let installed = false;

function normalizeNuvioRequest(req) {
  const u = new URL(req.url || '/', 'http://local');
  const parts = u.pathname.split('/').filter(Boolean);
  const resources = new Set(['manifest.json', 'catalog', 'meta', 'stream']);
  const resourceIndex = parts.findIndex((p) => resources.has(p) || p.startsWith('catalog') || p.startsWith('meta') || p.startsWith('stream'));

  if (resourceIndex < 0) return;

  const before = parts.slice(0, resourceIndex).filter((p) => p !== 'v527');
  if (!before.length) return;

  // Nuvio may send any of these:
  // /v527/<token>/manifest.json
  // /<token>/v527/manifest.json
  // /<token>/manifest.json
  const token = before[before.length - 1];
  if (!token || token.includes('..')) return;

  const resourcePath = '/' + parts.slice(resourceIndex).join('/');
  u.pathname = resourcePath;
  u.searchParams.set('config', token);
  req.url = u.pathname + (u.search || '');
}

express.application.use = function patchedUse(...args) {
  if (!installed) {
    installed = true;
    originalUse.call(this, (req, res, next) => {
      try {
        normalizeNuvioRequest(req);
      } catch (err) {
        console.error('XSportsX Nuvio route normalization error:', err.message);
      }
      next();
    });
  }
  return originalUse.apply(this, args);
};

require('./server.js');
