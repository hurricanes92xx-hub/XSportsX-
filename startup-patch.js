import fs from "node:fs";

const file = new URL("./sports-router.js", import.meta.url);
let source = fs.readFileSync(file, "utf8");

// Fix the stream-route hang: the old resolver called itself recursively.
source = source.replace(
  /async function resolveEventMeta\(id\)\{[\s\S]*?\nfunction manifest\(\)/,
  `async function resolveEventMeta(id){
 const raw=String(id).replace(/^sport:/,"");
 const cached=eventCache.get(id);if(cached)return cached;
 for(const l of Object.keys(LEAGUES)){
  try{const r=l==="ufc"?await ufcCatalog():await leagueCatalog(l);const f=r.find(x=>String(x.eventId)===raw||String(x.event?.id)===raw||String(x.id)===id);if(f){eventCache.set(id,f);return f}}catch{}
 }
 return null;
}
function manifest()`
);

// Replace the slow 500-channel resolver with a bounded universal resolver.
const start=source.indexOf("async function streamsForEvent");
const end=source.indexOf("async function ufcCatalog",start);
if(start>=0&&end>start){
 const resolver=`async function streamsForEvent(c,meta){
 if(!c||!meta?.event)return[];
 const key=\`fastmatch:\${c.server}|\${c.username}|\${meta.id}\`,cached=matchCache.get(key);
 if(cached&&Date.now()-cached.at<30000)return cached.value;
 const d=await xtreamData(c),all=Array.isArray(d.metas)?d.metas:[],e=meta.event,rows=[],seen=new Set();
 const home=teamTokens(e.home||{}),away=teamTokens(e.away||{}),bc=(e.broadcast||[]).map(norm).filter(Boolean);
 const scoreText=(m,text,bonus=0)=>{const t=norm(text),h=home.some(x=>x&&t.includes(x)),a=away.some(x=>x&&t.includes(x));let s=h&&a?100:(h||a?55:0);if(bc.some(x=>x&&t.includes(x)))s=100;return Math.min(100,s+bonus)};
 const add=(m,s,p)=>{if(!m?.xtream?.streamUrl||seen.has(m.id)||s<25)return;seen.add(m.id);const pt=decode(p?.title||""),pd=decode(p?.description||"");rows.push({name:\`▶ \${m.name}\`,url:m.xtream.streamUrl,title:m.name,description:\`\${m.xtream.category||"Live TV"} • match \${Math.round(s)}%\${pt?\` • \${pt}\`:""}\${pd?\` — \${pd.slice(0,220)}\`:""}\`,behaviorHints:{isLive:true}})};
 // First pass is immediate and covers every channel name/category.
 for(const m of all){const s=scoreText(m,\`\${m.name} \${m.xtream.category}\`);if(s)add(m,s,null)}
 // EPG pass: every provider channel remains eligible; only the best 96 are queried.
 const candidates=all.filter(m=>!seen.has(m.id)).slice(0,96);let cursor=0;const hits=[];
 const worker=async()=>{while(true){const n=cursor++;if(n>=candidates.length)return;const m=candidates[n];try{const epg=await getEpg(c,m.xtream.streamId);for(const p of epg||[]){let s=scoreText(m,\`\${p.title||""} \${p.description||""}\`,p.now_playing===1||p.now_playing==="1"?15:0);if(s>=35)hits.push({m,s,p})}}catch{}}};
 await Promise.race([Promise.all(Array.from({length:Math.min(12,candidates.length||1)},worker)),new Promise(r=>setTimeout(r,6000))]);
 for(const h of hits.sort((a,b)=>b.s-a.s).slice(0,32))add(h.m,h.s,h.p);
 // Never leave Nuvio waiting forever. If the provider has live channels but no EPG, return candidates.
 if(!rows.length)for(const m of all.filter(x=>x?.xtream?.streamUrl).slice(0,8))add(m,25,null);
 const value=rows.slice(0,32);matchCache.set(key,{at:Date.now(),value});return value;
}
`;
 source=source.slice(0,start)+resolver+source.slice(end);
}

fs.writeFileSync(file,source,"utf8");
console.log("[XSportsX] boot patch applied: fixed recursive meta resolver + bounded all-channel EPG source matcher");
// Do not spawn the backend here. render-entry-v528.js owns the single backend
// child process and will start it after this patch has been applied. Spawning
// here too caused two processes to bind INTERNAL_PORT=7099 and exit with status 1.
