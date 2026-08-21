// Compatibility layer for existing and current XSportsX installs.
// Keep the application routes stable while accepting the URL shapes Nuvio/Stremio may request.
const http = require('http');
const originalEmit = http.Server.prototype.emit;
http.Server.prototype.emit = function (event, req, res) {
  if (event === 'request' && req && typeof req.url === 'string') {
    let u = req.url;
    // Older XSportsX installs used /v527 as a base path.
    if (u === '/v527') u = '/';
    else if (u.startsWith('/v527/')) u = u.slice(5);
    // The server's canonical live-TV handlers use /channel. Accept the
    // standards-compatible /tv form too, without breaking cached manifests.
    u = u.replace(/^\/(catalog|meta|stream)\/tv\//, '/$1/channel/');
    req.url = u;
  }
  return originalEmit.call(this, event, req, res);
};
