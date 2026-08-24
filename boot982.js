const fs=require('fs');
const Module=require('module');
const path=require('path');
let source=fs.readFileSync(path.join(__dirname,'app98.js'),'utf8')
  .replace("const VERSION='9.8.0'", "const VERSION='9.8.2'")
  .replace("id:'community.xsportsx'", "id:'community.xsportsx982'")
  .replace("r.setHeader('content-type',t)}", "r.setHeader('content-type',t);r.setHeader('strict-transport-security','max-age=31536000; includeSubDomains');r.setHeader('x-content-type-options','nosniff');r.setHeader('referrer-policy','strict-origin-when-cross-origin');r.setHeader('content-security-policy','upgrade-insecure-requests')}")
  .replace("const u=new URL(req.url,`http://${req.headers.host||'localhost'}`),p=u.pathname;", "const proto=String(req.headers['x-forwarded-proto']||'https').split(',')[0].trim()||'https';const u=new URL(req.url,`${proto}://${req.headers.host||'localhost'}`),p=u.pathname;");
const m=new Module(path.join(__dirname,'app98.js'),module);
m.filename=path.join(__dirname,'app98.js');
m.paths=module.paths;
m._compile(source,m.filename);
