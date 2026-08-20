import fs from "node:fs";

const file = new URL("./sports-router.js", import.meta.url);
let source = fs.readFileSync(file, "utf8");

const broken = 'async function resolveEventMeta(id){const h=await resolveEventMeta(id);if(h)return h;';
const fixed = 'async function resolveEventMeta(id){const cached=eventCache.get(id);if(cached)return cached;';
source = source.replace(broken, fixed);
source = source.replace(/async function resolveEventMeta\(id\)\{\s*const h=await resolveEventMeta\(id\);\s*if\(h\)return h;/,'async function resolveEventMeta(id){const cached=eventCache.get(id);if(cached)return cached;');
source = source.replace(').slice(0,500);', ').slice(0,24);');
source = source.replace('u.toString(),5000)', 'u.toString(),1800)');
source = source.replace('f.toString(),5000)', 'f.toString(),1800)');
source = source.replace('set("limit","20")', 'set("limit","10")');

const marker = "// XSPORTSX_UNIVERSAL_STREAM_MATCHER_V1";
const firstStream = source.indexOf("async function streamsForEvent");
const lastStream = source.lastIndexOf("async function streamsForEvent");
if (lastStream > firstStream) source = source.slice(0, lastStream);
const markerAt = source.indexOf(marker);
if (markerAt >= 0) source = source.slice(0, markerAt);
if (!source.includes(marker)) {
  const universal = `
${marker}
async function streamsForEvent(c,meta){if(!c||!meta?.event)return[];const k="universal-match:"+c.server+"|"+c.username+"|"+meta.id,h=matchCache.get(k);if(h&&Date.now()-h.at<60000)return h.value;const d=await xtreamData(c),all=Array.isArray(d.metas)?d.metas:[],rows=[],seen=new Set(),event=meta.event;
const addOne=(m,s,e)=>{if(!m?.xtream?.streamUrl||seen.has(m.id)||s<45)return;seen.add(m.id);add(rows,seen,m,Math.min(100,Math.round(s)),e)};
for(const m of all){const t=norm((m.name||"")+" "+(m.xtream?.category||""));let s=0;for(const x of [...teamTokens(event.home||{}),...teamTokens(event.away||{})])if(x&&t.includes(x))s+=x.length>=5?52:32;for(const b of event.broadcast||[])if(norm(b)&&t.includes(norm(b)))s=100;if(meta.league==="ufc"&&/\b(ufc|mma|fight|ppv|combat)\b/i.test(t))s+=40;if(s>=45)addOne(m,s,null)}
let idx=0;const hits=[];const worker=async()=>{while(true){const n=idx++;if(n>=all.length)return;const m=all[n],sid=m.xtream?.streamId;if(!sid||seen.has(m.id))continue;try{const epg=await getEpg(c,sid);let best=0,be=null;for(const p of epg||[]){const s=score(m,p,meta);if(s>best){best=s;be=p}}if(best>=45)hits.push({m,best,be})}catch{}}};
await Promise.race([Promise.all(Array.from({length:Math.min(24,Math.max(1,all.length))},worker)),new Promise(r=>setTimeout(r,8000))]);
for(const x of hits.sort((a,b)=>b.best-a.best).slice(0,24))addOne(x.m,x.best,x.be);
const value=rows.sort((a,b)=>(b.score||0)-(a.score||0)).slice(0,16);matchCache.set(k,{at:Date.now(),value});return value}
`;
  const re = /async function streamsForEvent\(.*?\}async function ufcCatalog/s;
  if (!re.test(source)) throw new Error("Could not locate streamsForEvent in sports-router.js");
  source = source.replace(re, universal + "async function ufcCatalog");
}

fs.writeFileSync(file, source, "utf8");
console.log("[XSportsX] Universal all-channel stream matcher installed safely.");
