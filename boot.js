const fs = require('fs');
const path = require('path');
const http = require('http');

// Render terminates TLS at its proxy. app96 builds absolute URLs from req.url,
// so make the incoming request URL absolute-HTTPS before the app sees it.
const originalCreateServer = http.createServer;
http.createServer = function wrappedCreateServer(handler) {
  return originalCreateServer.call(http, (req, res) => {
    if (req.url && req.url.startsWith('/')) {
      const host = req.headers.host || 'localhost';
      req.url = `https://${host}${req.url}`;
    }
    return handler(req, res);
  });
};

const appPath = path.join(__dirname, 'app96.js');
let source = fs.readFileSync(appPath, 'utf8');
const bad = "return json(res,200,{ok:true,version:VERSION})}if(req.method==='GET'&&u.pathname==='/artwork.svg')";
const good = "return json(res,200,{ok:true,version:VERSION});if(req.method==='GET'&&u.pathname==='/artwork.svg')";
if (source.includes(bad)) source = source.replace(bad, good);
fs.writeFileSync(appPath, source);
require(appPath);
