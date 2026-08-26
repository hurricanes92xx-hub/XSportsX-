const {publicChannels}=require('./public-sources');
const {healthRank}=require('./live-source-policy');

const CACHE_TTL=Number(process.env.PUBLIC_API_CACHE_TTL_SECONDS||120)*1000;
let cache={expires:0,value:[]};
let inflight=null;

async function getPublicStreams(){
  if(cache.expires>Date.now()) return cache.value;
  if(inflight) return inflight;
  inflight=(async()=>{
    const channels=await publicChannels();
    const healthy=await healthRank(channels);
    const value=healthy.map((x,i)=>({
      id:`public:${x.streamId}`,
      type:'tv',
      name:x.name,
      group:x.group||x.category||'Sports',
      url:x.url,
      logo:x.logo||'',
      sourceId:x.sourceId,
      sourceName:x.sourceName,
      health:x.health,
      rank:i+1
    }));
    cache={expires:Date.now()+CACHE_TTL,value};
    return value;
  })().finally(()=>{inflight=null});
  return inflight;
}

module.exports={getPublicStreams};
