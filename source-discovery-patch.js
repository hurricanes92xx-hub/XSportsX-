import fs from 'node:fs';

const entry = new URL('./render-entry-v528.js', import.meta.url);
let s = fs.readFileSync(entry, 'utf8');

const helper = String.raw`
async function xsportsxDirectSourceScan(site){
  const out=[];
  let page;
  try{page=await fetch(site,{redirect:'follow',headers:{accept:'text/plain,text/html,application/json,*/*'},signal:AbortSignal.timeout(9000)});}catch{return {records:[],credentialed:0,healthy:0};}
  if(!page.ok)return {records:[],credentialed:0,healthy:0};
  let text='';try{text=(await page.text()).slice(0,2000000);}catch{return {records:[],credentialed:0,healthy:0};}
  const urls=[...new Set((text.match(/https?:\\/\\/[^\\s"'<>]+/gi)||[]).map(x=>x.replace(/[\\]\\[),;]+$/g,'')))];
  let credentialed=0,healthy=0;
  for(const raw of urls.slice(0,200)){
    let u;try{u=new URL(raw);}catch{continue;}
    if(!['http:','https:'].includes(u.protocol))continue;
    const q=u.searchParams,path=u.pathname.toLowerCase(),all=raw.toLowerCase();
    const hasCred=q.has('username')||q.has('password')||q.has('user')||q.has('pass');
    let type='direct';
    if(q.get('type')?.toLowerCase().includes('m3u')||path.includes('get.php')||all.includes('m3u_plus'))type='m3u';
    else if(path.includes('player_api.php')||all.includes('xtream'))type='xtream';
    else if(path.includes('portal.php')||all.includes('stalker'))type='stalker';
    else if(/\\.(m3u8?|mpd)(?:$|[?#])/i.test(path))type='m3u';
    if(!['m3u','xtream','stalker'].includes(type))continue;
    if(hasCred){credentialed++;out.push({url:u.origin+u.pathname,type,server:u.origin,healthy:false,credentialPresent:true,requiresManualCredentials:true,details:'Credentialed IPTV record detected. Credentials are hidden and must be entered from an authorized account.'});continue;}
    try{const started=Date.now(),r=await fetch(u,{method:'HEAD',redirect:'manual',signal:AbortSignal.timeout(6000),headers:{'user-agent':'XSportsX-LinkHealth/1.0'}}),ok=r.ok||(r.status>=300&&r.status<400);out.push({url:u.href,type,server:u.origin,healthy:ok,status:r.status,latencyMs:Date.now()-started,details:ok?'Direct IPTV endpoint found':'Direct IPTV endpoint failed'});if(ok)healthy++;}catch{out.push({url:u.href,type,server:u.origin,healthy:false,details:'Direct IPTV endpoint health check failed'});}
  }
  return {records:[...new Map(out.map(x=>[`${x.type}|${x.server}|${x.url}`,x])).values()],credentialed,healthy};
}
`;
if(!s.includes('async function xsportsxDirectSourceScan'))s=s.replace('const sourceCache=new Map();',helper+'\nconst sourceCache=new Map();');
const oldFn=/async function getSourceStateByToken\(token\)\{[\s\S]*?return discoverReddit\(token,config,state\)\}/;
const newFn=String.raw`async function getSourceStateByToken(token){
 if(!token)return null;
 const state=loadSourceState(token);
 const config=decryptConfig('/'+PUBLIC_PREFIX+'/'+encodeURIComponent(token)+'/manifest.json');
 if(!config)return null;
 state.diagnostics=state.diagnostics||{postsChecked:0,base64Decoded:0,destinationsFetched:0,m3u:0,xtream:0,stalker:0,credentialedRecords:0};
 if(config.sourceUrl){try{
  const scan=await scanBase64Input({site:config.sourceUrl,health:true});state.diagnostics.base64Decoded=scan.decodedCount||0;state.diagnostics.destinationsFetched=scan.linkCount||0;
  for(const x of (scan.links||[]).filter(x=>x.ok)){const item={url:x.url,type:'direct',healthy:true,status:x.status,latencyMs:x.latencyMs,details:'Discovered from approved source'};if(!state.approved.some(a=>a.url===item.url)&&!state.rejected.includes(item.url)&&!state.pending.some(a=>a.url===item.url))state.pending.push(item);}
  const direct=await xsportsxDirectSourceScan(config.sourceUrl);state.diagnostics.m3u+=(direct.records||[]).filter(x=>x.type==='m3u').length;state.diagnostics.xtream+=(direct.records||[]).filter(x=>x.type==='xtream').length;state.diagnostics.stalker+=(direct.records||[]).filter(x=>x.type==='stalker').length;state.diagnostics.credentialedRecords+=direct.credentialed||0;
  for(const item of (direct.records||[])){if(state.approved.some(a=>a.url===item.url)||state.rejected.includes(item.url)||state.pending.some(a=>a.url===item.url))continue;state.pending.push(item);}
 }catch(e){console.error('Source discovery failed:',e.message)}}
 const result=await discoverReddit(token,config,state);saveSourceState(token,result);return result;
}`;
if(oldFn.test(s))s=s.replace(oldFn,newFn);
fs.writeFileSync(entry,s,'utf8');
console.log('[XSportsX] source discovery patch loaded: plain IPTV records on decoded/source pages are now visible to Source Manager.');
