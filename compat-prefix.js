// Render/Nuvio compatibility: older XSportsX installs used /v527 as the addon base path.
// Strip that prefix before Express routing so both /... and /v527/... work.
const http = require('http');
const originalEmit = http.Server.prototype.emit;
http.Server.prototype.emit = function (event, req, res) {
  if (event === 'request' && req && typeof req.url === 'string' && req.url === '/v527') req.url = '/';
  else if (event === 'request' && req && typeof req.url === 'string' && req.url.startsWith('/v527/')) req.url = req.url.slice(5);
  return originalEmit.call(this, event, req, res);
};
