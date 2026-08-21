// Render/Nuvio compatibility for existing XSportsX installs.
// 1) Older addon URLs used /v527 as a base path.
// 2) Some cached manifests used the older channel content type.
const http = require('http');
const originalEmit = http.Server.prototype.emit;
http.Server.prototype.emit = function (event, req, res) {
  if (event === 'request' && req && typeof req.url === 'string') {
    let u = req.url;
    if (u === '/v527') u = '/';
    else if (u.startsWith('/v527/')) u = u.slice(5);
    u = u.replace(/^\/(catalog|meta|stream)\/channel\//, '/$1/tv/');
    req.url = u;
  }
  return originalEmit.call(this, event, req, res);
};
