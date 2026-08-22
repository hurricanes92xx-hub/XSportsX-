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
  if(parts[0]==='v527') parts=parts.slice(1);
  if(parts.length===2 && parts[1]==='manifest.json'){
    const token=parts[0];
    u.pathname='/manifest.json';
    u.searchParams.set('config',token);
    return u.pathname+(u.search||'');
  }
  const reserved=new Set(['manifest.json','configure','health','xtream-health','artwork','catalog','meta','stream']);
  if(parts.length>1 && !reserved.has(parts[0]) && !parts[0].endsWith('.json')){
    const token=parts.shift();
    u.pathname='/'+parts.join('/');
    u.searchParams.set('config',token);
  }
  return u.pathname+(u.search||'');
}

function configuredManifest(res){
  const body=JSON.stringify({id:'community.xsportsx',version:'5.2.0',name:'XSportsX',description:'XSportsX live sports with configurable Xtream or M3U sources.',logo:'/artwork/other.svg',resources:['catalog','meta','stream'],types:['tv'],idPrefixes:['sport:','league:']});
  res.writeHead(200,{'content-type':'application/json; charset=utf-8','cache-control':'no-store, max-age=0'});res.end(body);
}

const proxy=http.createServer((req,res)=>{
  const raw=req.url||'/';
  let incoming;
  try{incoming=new URL(raw,'http://local')}catch{res.statusCode=400;return res.end('Bad request')}
  let parts=incoming.pathname.split('/').filter(Boolean);
  if(parts[0]==='v527')parts=parts.slice(1);
  if(parts.length===2 && parts[1]==='manifest.json' && parts[0].length>20){
    return configuredManifest(res);
  }
  const path=rewrite(raw);
  const headers={...req.headers,host:req.headers.host||'localhost','x-forwarded-proto':req.headers['x-forwarded-proto']||'https'};
  const r=http.request({hostname:'127.0.0.1',port:internalPort,path,method:req.method,headers},up=>{
    res.writeHead(up.statusCode||502,up.headers);up.pipe(res);
  });
  r.on('error',err=>{res.statusCode=502;res.end(`XSportsX proxy error: ${err.message}`)});
  req.pipe(r);
});
proxy.listen(publicPort,'0.0.0.0',()=>console.log(`XSportsX proxy listening on ${publicPort}, app on ${internalPort}`));
