const http = require('http');
const crypto = require('crypto');

const PORT = Number(process.env.PAIRING_PORT || process.env.PORT || 10001);
const PAIR_TTL_MS = 5 * 60 * 1000;
const sessions = new Map();
const devices = new Map();

function token(bytes = 24) { return crypto.randomBytes(bytes).toString('base64url'); }
function json(res, status, body) { res.writeHead(status, {'content-type':'application/json; charset=utf-8','cache-control':'no-store'}); res.end(JSON.stringify(body)); }
function body(req) { return new Promise((resolve,reject)=>{let b='';req.on('data',c=>{b+=c;if(b.length>20000) req.destroy();});req.on('end',()=>{try{resolve(b?JSON.parse(b):{})}catch(e){reject(e)}});req.on('error',reject);}); }
function cleanup(){const now=Date.now();for(const [k,v] of sessions)if(v.expires<now)sessions.delete(k);}

const server=http.createServer(async(req,res)=>{
  cleanup();
  const u=new URL(req.url || '/', `http://${req.headers.host || 'localhost'}`);
  try {
    if(req.method==='GET' && u.pathname==='/pair/start') {
      const pairCode = token(9);
      const sessionId = token(18);
      sessions.set(pairCode,{sessionId,expires:Date.now()+PAIR_TTL_MS,approved:false,deviceToken:null});
      return json(res,200,{ok:true,pairCode,sessionId,expiresIn:300,qrPayload:`xsportsx://pair/${pairCode}`});
    }
    if(req.method==='POST' && u.pathname==='/pair/approve') {
      const b=await body(req); const s=sessions.get(String(b.pairCode||''));
      if(!s || s.expires<Date.now()) return json(res,410,{ok:false,error:'Pairing code expired'});
      if(!b.accountToken || String(b.accountToken).length<16) return json(res,401,{ok:false,error:'Authenticated phone required'});
      s.approved=true; s.deviceToken=token(32); s.accountToken=String(b.accountToken);
      return json(res,200,{ok:true,deviceToken:s.deviceToken,sessionId:s.sessionId});
    }
    if(req.method==='POST' && u.pathname==='/pair/complete') {
      const b=await body(req); const s=[...sessions.values()].find(x=>x.sessionId===b.sessionId);
      if(!s || s.expires<Date.now() || !s.approved || s.deviceToken!==b.deviceToken) return json(res,403,{ok:false,error:'Pairing not approved'});
      const deviceId=token(12); devices.set(deviceId,{deviceId,accountToken:s.accountToken,createdAt:new Date().toISOString()}); sessions.delete([...sessions.keys()].find(k=>sessions.get(k)===s));
      return json(res,200,{ok:true,deviceId});
    }
    if(req.method==='GET' && u.pathname==='/health') return json(res,200,{ok:true,name:'XSportsX Pairing',activeSessions:sessions.size,devices:devices.size});
    return json(res,404,{ok:false,error:'Not found'});
  } catch(e) { return json(res,500,{ok:false,error:'Pairing service error'}); }
});
server.listen(PORT,'0.0.0.0',()=>console.log(`XSportsX pairing service listening on ${PORT}`));
