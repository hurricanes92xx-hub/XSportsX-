const http=require('http');
const {URL}=require('url');
const publicPort=Number(process.env.PORT||10000);
const internalPort=publicPort+1;
process.env.PORT=String(internalPort);
require('./compat-prefix.js');
require('./server.js');

function rewrite(path){
  const u=new URL(path,'http://local');
  let parts=u.pathname.split('/').filter(Boolean);
  if(parts[0]==='v527')parts=parts.slice(1);

  // Only strip a configured XSportsX token. Normal application routes such
  // as /catalog/tv/... and /artwork/... must pass through untouched.
  if(parts.length>1){
    const token=parts[0];
    const looksSigned=token && token.length>20 && token.split('.').length===3;
    if(looksSigned){
      parts.shift();
      u.pathname='/'+parts.join('/');
      u.searchParams.set('config',token);
    }
  }
  return u.pathname+(u.search||'');
}

const proxy=http.createServer((req,res)=>{
  try{
    const raw=req.url||'/';
    const path=rewrite(raw);
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
