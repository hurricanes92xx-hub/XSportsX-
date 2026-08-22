// Compatibility layer for existing XSportsX installs.
// Canonical application routes are the live-TV `tv` routes. Older cached
// Nuvio manifests use `channel`, and older XSportsX installs used `/v527`.
const http = require('http');
const originalEmit = http.Server.prototype.emit;
http.Server.prototype.emit = function (event, req, res) {
  if (event === 'request' && req && typeof req.url === 'string') {
    let u = req.url;
    if (u === '/v527') u = '/';
    else if (u.startsWith('/v527/')) u = u.slice('/v527'.length);

    // Configured manifests are emitted as /<signed-token>/manifest.json.
    // Route them to the canonical endpoint while preserving the signed token
    // as ?config= so the application can load the matching Xtream/M3U config.
    const m = u.match(/^\/([^/?]+\.[^/?]+)(\/.*)?(\?.*)?$/);
    if (m && m[1] && m[1].length > 20 && m[2]) {
      const token = m[1];
      const rest = m[2] || '/';
      const query = m[3] ? `${m[3]}&config=${encodeURIComponent(token)}` : `?config=${encodeURIComponent(token)}`;
      u = `${rest}${query}`;
    }

    u = u.replace(/^\/(catalog|meta|stream)\/channel\//, '/$1/tv/');
    // Versioned poster path: the server handler remains the canonical event
    // renderer, but Nuvio sees a genuinely new URL after every card revision.
    u = u.replace(/^\/artwork\/event-v7\//, '/artwork/event/');
    req.url = u;
  }
  return originalEmit.call(this, event, req, res);
};
