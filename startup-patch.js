import fs from "node:fs";

const file = new URL("./sports-router.js", import.meta.url);
let source = fs.readFileSync(file, "utf8");

// Keep configuration tokens valid across the gateway/backend prefix versions.
source = source.replace('const i=p.indexOf(PREFIX);', 'const i=[PREFIX,"v527","v526","v528","v529","v530","v523"].map(x=>p.indexOf(x)).find(x=>x>=0);');

// Fix the metadata recursion if an older router is deployed.
source = source.replace('async function resolveEventMeta(id){const h=await resolveEventMeta(id);if(h)return h;', 'async function resolveEventMeta(id){const cached=eventCache.get(id);if(cached)return cached;');
source = source.replace(/async function resolveEventMeta\(id\)\{\s*const h=await resolveEventMeta\(id\);\s*if\(h\)return h;/,'async function resolveEventMeta(id){const cached=eventCache.get(id);if(cached)return cached;');
source = source.replace(').slice(0,500);', ').slice(0,64);');
source = source.replace('u.toString(),5000)', 'u.toString(),2500)');
source = source.replace('f.toString(),5000)', 'f.toString(),2500)');

const marker = "// XSPORTSX_UNIVERSAL_STREAM_MATCHER_V2";
const firstStream = source.indexOf("async function streamsForEvent");
const lastStream = source.lastIndexOf("async function streamsForEvent");
if (lastStream > firstStream) source = source.slice(0, lastStream);
const markerAt = source.indexOf(marker);
if (markerAt >= 0) source = source.slice(0, markerAt);

if (!source.includes(marker)) {
  const universal = `
${marker}
async function streamsForEvent(c,meta){
  if(!c||!meta?.event)return[];
  const k="universal-match:"+c.server+"|"+c.username+"|"+meta.id;
  const h=matchCache.get(k);if(h&&Date.now()-h.at<60000)return h.value;
  const d=await xtreamData(c),all=Array.isArray(d.metas)?d.metas:[],rows=[],seen=new Set(),event=meta.event;
  const addOne=(m,s,e)=>{if(!m?.xtream?.streamUrl||seen.has(m.id))return;seen.add(m.id);add(rows,seen,m,Math.min(100,Math.round(s)),e)};
  const eventTerms=[...teamTokens(event.home||{}),...teamTokens(event.away||{})].filter(Boolean);

  // Pass 1: channel names/categories, with NO sports-category restriction.
  for(const m of all){
    const t=norm((m.name||"")+" "+(m.xtream?.category||""));let s=0;
    for(const x of eventTerms)if(t.includes(x))s=Math.max(s,x.length>=5?70:45);
    for(const b of event.broadcast||[])if(norm(b)&&t.includes(norm(b)))s=100;
    if(meta.league==="ufc"&&/\b(ufc|mma|fight|ppv|combat)\b/i.test(t))s=Math.max(s,60);
    if(s>=40)addOne(m,s,null);
  }

  // Pass 2: provider EPG. Every channel is eligible, including ordinary
  // entertainment/news/local channels. Query in bounded parallel batches.
  let idx=0;const hits=[];
  const worker=async()=>{while(true){const n=idx++;if(n>=all.length)return;const m=all[n],sid=m.xtream?.streamId;if(!sid||seen.has(m.id))continue;try{const epg=await getEpg(c,sid);let best=0,be=null;for(const p of epg||[]){const title=decode(p?.title||""),desc=decode(p?.description||""),text=title+" "+desc;let s=score(m,p,meta);for(const x of eventTerms)if(x&&norm(text).includes(x))s=Math.max(s,x.length>=5?78:52);if(p?.now_playing===1||p?.now_playing==="1")s+=12;if(s>best){best=s;be=p}}if(be)hits.push({m,best,be})}catch{}}};
  await Promise.race([Promise.all(Array.from({length:Math.min(32,Math.max(1,all.length))},worker)),new Promise(r=>setTimeout(r,15000))]);
  for(const x of hits.sort((a,b)=>b.best-a.best).slice(0,48))if(x.best>=35)addOne(x.m,x.best,x.be);

  // Pass 3: if exact matching still produced nothing, return currently-live
  // provider channels as a visible fallback. This prevents a provider with
  // incomplete/mislabelled EPG from producing "No streams found".
  if(rows.length===0){
    const fallback=[];let j=0;
    const fw=async()=>{while(true){const n=j++;if(n>=all.length)return;const m=all[n],sid=m.xtream?.streamId;if(!sid)continue;try{const epg=await getEpg(c,sid);for(const p of epg||[]){let s=10;if(p?.now_playing===1||p?.now_playing==="1")s+=35;const text=norm((p?.title||"")+" "+(p?.description||""));for(const x of eventTerms)if(x&&text.includes(x))s+=x.length>=5?35:20;fallback.push({m,s,p})}}catch{}}};
    await Promise.race([Promise.all(Array.from({length:Math.min(32,Math.max(1,all.length))},fw)),new Promise(r=>setTimeout(r,15000))]);
    for(const x of fallback.sort((a,b)=>b.s-a.s).slice(0,24))addOne(x.m,Math.min(44,x.s),x.p);
  }

  rows.sort((a,b)=>(b.score||0)-(a.score||0));const value=rows.slice(0,24);matchCache.set(k,{at:Date.now(),value});return value;
}
`;
  // Match the existing resolver without escaping the parentheses twice.
  const re = /async function streamsForEvent\(.*?\}async function ufcCatalog/s;
  if (!re.test(source)) throw new Error("Could not locate streamsForEvent in sports-router.js");
  source = source.replace(re, universal + "async function ufcCatalog");
}

fs.writeFileSync(file, source, "utf8");
console.log("[XSportsX] V2 universal source matcher: all channels + all-channel EPG + live fallback enabled.");
