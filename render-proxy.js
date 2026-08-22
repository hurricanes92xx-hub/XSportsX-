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
  let parts=u.pathname.split('/').filter(Boolean);
  if(parts[0]==='v527')parts=parts.slice(1);

  // A configured Nuvio addon is /<token>/<resource>. The token may be
  // encrypted (three dot-separated segments) or a legacy opaque token.
  // Only rewrite when the second segment is a real addon resource.
  if(parts.length>=2 && !PUBLIC_ROUTES.has(parts[0]) && PRIVATE_RESOURCES.has(parts[1])){
    const token=parts.shift();
    u.pathname='/'+parts.join('/');
    u.searchParams.set('config',token);
  }
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
