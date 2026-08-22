const http=require('http');
const {URL}=require('url');
const publicPort=Number(process.env.PORT||10000);
const internalPort=publicPort+1;
process.env.PORT=String(internalPort);
require('./compat-prefix.js');
require('./server.js');

const catalogs=[
  ['sports-command-center','🏆 XSPORTSX • SPORTS COMMAND CENTER'],
  ['live-now','🔴 LIVE NOW'],
  ['starting-soon','⏰ STARTING SOON'],
  ['nfl','🏈 NFL'],['ncaaf','🏈 NCAA FOOTBALL'],['nba','🏀 NBA'],['wnba','🏀 WNBA'],
  ['ncaab','🏀 NCAA BASKETBALL'],['mlb','⚾ MLB'],['nhl','🏒 NHL'],['mls','⚽ MLS'],
  ['epl','⚽ PREMIER LEAGUE'],['ucl','⚽ UEFA CHAMPIONS LEAGUE'],['laliga','⚽ LA LIGA'],
  ['seriea','⚽ SERIE A'],['bundesliga','⚽ BUNDESLIGA'],['ligue1','⚽ LIGUE 1'],
  ['ufc','🥊 UFC'],['boxing','🥊 BOXING'],['iptv-live','📡 MY IPTV • LIVE TV']
];
const baseManifest={
  id:'community.xsportsx',version:'5.2.1',name:'XSportsX',
  description:'XSportsX live sports with cinematic matchup cards and configurable Xtream or M3U sources.',
  resources:[{name:'catalog',types:['channel']},{name:'meta',types:['channel']},{name:'stream',types:['channel']}],
  types:['channel'],idPrefixes:['sport:','league:','live:','xtream:'],
  catalogs:catalogs.map(([id,name])=>({type:'channel',id,name,extra:[],showInHome:true})),
  behaviorHints:{configurable:false,configurationRequired:false},logo:'/artwork/other.svg'
};
function rewrite(path){
  const u=new URL(path,'http://local');
  let parts=u.pathname.split('/').filter(Boolean);
  if(parts[0]==='v527')parts=parts.slice(1);
  if(parts.length>1){
    const token=parts.shift();
    if(token&&token!=='manifest.json'&&!token.endsWith('.json')){u.pathname='/'+parts.join('/');u.searchParams.set('config',token);}
  }
  return u.pathname+(u.search||'');
}
function configuredManifest(res){
  res.writeHead(200,{'content-type':'application/json; charset=utf-8','cache-control':'no-store, max-age=0','access-control-allow-origin':'*','x-xsportsx-route':'edge-manifest','x-xsportsx-version':'5.2.1'});
  res.end(JSON.stringify(baseManifest));
}
const proxy=http.createServer((req,res)=>{
  const raw=req.url||'/';
  let incoming;
  try{incoming=new URL(raw,'http://local')}catch{res.statusCode=400;return res.end('Bad request')}
  let parts=incoming.pathname.split('/').filter(Boolean);
  if(parts[0]==='v527')parts=parts.slice(1);
  if(parts.length>=1){
    const last=decodeURIComponent(parts[parts.length-1]||'');
    if(last==='manifest.json')return configuredManifest(res);
  }
  const path=rewrite(raw);
  const headers={...req.headers,host:req.headers.host||'localhost','x-forwarded-proto':req.headers['x-forwarded-proto']||'https'};
  const r=http.request({hostname:'127.0.0.1',port:internalPort,path,method:req.method,headers},up=>{res.writeHead(up.statusCode||502,up.headers);up.pipe(res);});
  r.on('error',err=>{res.statusCode=502;res.end(`XSportsX proxy error: ${err.message}`)});
  req.pipe(r);
});
proxy.listen(publicPort,'0.0.0.0',()=>console.log(`XSportsX proxy listening on ${publicPort}, app on ${internalPort}`));
