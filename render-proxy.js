const http=require('http');
const {URL}=require('url');
const publicPort=Number(process.env.PORT||10000);
const internalPort=publicPort+1;
process.env.PORT=String(internalPort);
require('./server.js');

const PUBLIC_ROUTES=new Set(['manifest.json','configure','health','xtream-health','artwork','catalog','meta','stream','qr']);
const PRIVATE_RESOURCES=new Set(['manifest.json','catalog','meta','stream']);

function rewrite(path){
  const u=new URL(path,'http://local');
  const original=u.pathname.split('/').filter(Boolean);
  let parts=[...original];

  // Nuvio has used both forms in different compatibility paths:
  //   /v527/<token>/manifest.json
  //   /<token>/v527/manifest.json
  // and the normal addon form:
  //   /<token>/manifest.json
  // Accept all three so the public Render endpoint is not sensitive to
  // where Nuvio inserts its compatibility prefix.
  if(parts[0]==='v527') parts.shift();

  const resourceIndex=parts.findIndex((p)=>PRIVATE_RESOURCES.has(p));
  if(resourceIndex>0){
    const tokenIndex=parts.findIndex((p,i)=>i<resourceIndex && p!=='v527' && !PUBLIC_ROUTES.has(p));
    if(tokenIndex>=0){
      const token=parts[tokenIndex];
      const resourceParts=parts.slice(resourceIndex);
      u.pathname='/'+resourceParts.join('/');
      u.searchParams.set('config',token);
      return u.pathname+(u.search||'');
    }
  }

  // Also tolerate /v527/<resource> for public routes.
  u.pathname='/'+parts.join('/');
  return u.pathname+(u.search||'');
}

const proxy=http.createServer((req,res)=>{
  try{
    const path=rewrite(req.url||'/');
    const headers={...req.headers,host:req.headers.host||'localhost','x-forwarded-proto':req.headers['x-forwarded-proto']||'https'};
    const r=http.request({hostname:'127.0.0.1',port:internalPort,path,method:req.method,headers},up=>{
      res.writeHead(up.statusCode||502,up.headers);
      up.pipe(res);
    });
    r.on('error',err=>{res.statusCode=502;res.end(`XSportsX proxy error: ${err.message}`)});
    req.pipe(r);
  }catch(e){res.statusCode=400;res.end('Bad request');}
});
proxy.listen(publicPort,'0.0.0.0',()=>console.log(`XSportsX Render proxy listening on ${publicPort}, app on ${internalPort}`));
