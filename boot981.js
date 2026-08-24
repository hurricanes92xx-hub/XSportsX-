const fs=require('fs');
const Module=require('module');
const path=require('path');
const appPath=path.join(__dirname,'app98.js');
let source=fs.readFileSync(appPath,'utf8')
  .replace("const VERSION='9.8.0'", "const VERSION='9.8.1'")
  .replace("id:'community.xsportsx'", "id:'community.xsportsx981'");

// Render terminates TLS at its edge proxy. Make every browser-facing response
// explicitly HTTPS-only so configuration forms and generated manifest URLs
// cannot fall back to http:// and trigger Chrome's "Not secure" warning.
const oldHdr="function hdr(r,t='application/json; charset=utf-8'){r.setHeader('access-control-allow-origin','*');r.setHeader('access-control-allow-methods','GET,POST,OPTIONS');r.setHeader('access-control-allow-headers','content-type');r.setHeader('cache-control','no-store');r.setHeader('x-xsportsx-version',VERSION);r.setHeader('content-type',t)}";
const newHdr="function hdr(r,t='application/json; charset=utf-8'){r.setHeader('access-control-allow-origin','*');r.setHeader('access-control-allow-methods','GET,POST,OPTIONS');r.setHeader('access-control-allow-headers','content-type');r.setHeader('cache-control','no-store');r.setHeader('x-xsportsx-version',VERSION);r.setHeader('strict-transport-security','max-age=31536000; includeSubDomains');r.setHeader('content-security-policy','upgrade-insecure-requests');r.setHeader('x-content-type-options','nosniff');r.setHeader('referrer-policy','strict-origin-when-cross-origin');r.setHeader('content-type',t)}";
if(source.includes(oldHdr))source=source.replace(oldHdr,newHdr);

// Trust Render's forwarded HTTPS scheme when the app builds absolute URLs.
source=source.replace(/const u=new URL\(req\.url,([^\n;]+)\)/g,"const u=new URL(req.url,`https://${req.headers.host||'localhost'}`)");

const m=new Module(appPath,module);
m.filename=appPath;
m.paths=module.paths;
m._compile(source,m.filename);
