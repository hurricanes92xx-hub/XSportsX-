const crypto=require('crypto');
const axios=require('axios');

const TIMEOUT=Number(process.env.PUBLIC_HEALTH_TIMEOUT_MS||3500);
const TTL=Number(process.env.PUBLIC_HEALTH_CACHE_TTL_SECONDS||120)*1000;
const cache=new Map();
const inflight=new Map();

// Only sources explicitly classified as public/authorized are eligible.
const APPROVED_HOSTS=new Set([
  'iptv-org.github.io','raw.githubusercontent.com','github.com',
  'wurl.com','amagi.tv','tubi.video','splus.ir','akamaized.net',
  'tjktv.org','rtatv.akamaized.net'
]);

function hostOf(url){try{return new URL(url).hostname.toLowerCase()}catch{return ''}}
function approved(url){const h=hostOf(url);return [...APPROVED_HOSTS].some(x=>h===x||h.endsWith(`.${x}`));}
function cacheGet(k){const x=cache.get(k);return x&&x.exp>Date.now()?x.v:null;}
async function probe(url){
  if(!approved(url)||!/^https:\/\//i.test(url))return {ok:false,reason:'policy'};
  const key=crypto.createHash('sha1').update(url).digest('hex');
  const hit=cacheGet(key);if(hit)return hit;
  if(inflight.has(key))return inflight.get(key);
  const p=(async()=>{
    const started=Date.now();
    try{
      const r=await axios.get(url,{timeout:TIMEOUT,responseType:'text',maxContentLength:2000000,validateStatus:s=>s>=200&&s<400,headers:{'User-Agent':'XSportsX-health/1.0','Accept':'application/vnd.apple.mpegurl,application/x-mpegURL,text/plain,*/*'}});
      const body=String(r.data||'');
      const hls=/^#EXTM3U/m.test(body);
      const segments=/^#EXTINF:/m.test(body)||/\.m4s(?:\?|$)|\.ts(?:\?|$)/mi.test(body);
      const v={ok:Boolean(hls&&segments),status:r.status,latencyMs:Date.now()-started,contentType:String(r.headers['content-type']||''),hls,segments,checkedAt:new Date().toISOString()};
      cache.set(key,{v,exp:Date.now()+TTL});return v;
    }catch(e){const v={ok:false,reason:e.code||e.message,latencyMs:Date.now()-started,checkedAt:new Date().toISOString()};cache.set(key,{v,exp:Date.now()+TTL});return v;}
  })().finally(()=>inflight.delete(key));
  inflight.set(key,p);return p;
}
async function healthRank(channels){
  const candidates=channels.filter(x=>x.public&&approved(x.url)).slice(0,80);
  const results=await Promise.all(candidates.map(async ch=>({...ch,health:await probe(ch.url)})));
  return results.filter(x=>x.health.ok).sort((a,b)=>(a.health.latencyMs||99999)-(b.health.latencyMs||99999));
}
module.exports={approved,probe,healthRank};
