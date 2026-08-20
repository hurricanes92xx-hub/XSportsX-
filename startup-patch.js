import fs from "node:fs";

const file = new URL("./sports-router.js", import.meta.url);
let source = fs.readFileSync(file, "utf8");

source = source.replace(
  'const i=p.indexOf(PREFIX);',
  'const i=[PREFIX,"v527","v526","v528","v529","v530","v523"].map(x=>p.indexOf(x)).find(x=>x>=0);'
);
source = source.replace(
  'async function resolveEventMeta(id){const h=await resolveEventMeta(id);if(h)return h;',
  'async function resolveEventMeta(id){const cached=eventCache.get(id);if(cached)return cached;'
);
source = source.replace(
  /async function resolveEventMeta\(id\)\{\s*const h=await resolveEventMeta\(id\);\s*if\(h\)return h;/,
  'async function resolveEventMeta(id){const cached=eventCache.get(id);if(cached)return cached;'
);

// Replace the resolver by function boundaries. This is idempotent and avoids
// the regex-based startup crashes from earlier builds.
const start = source.indexOf("async function streamsForEvent");
if (start >= 0) {
  const next = source.indexOf("async function ", start + 20);
  if (next > start) {
    const resolver = `async function streamsForEvent(c,meta){
  if(!c||!meta?.event)return[];
  const key=\`universal:\${c.server}|\${c.username}|\${meta.id}\`;
  const cached=matchCache.get(key);
  if(cached&&Date.now()-cached.at<30000)return cached.value;
  const d=await xtreamData(c),all=Array.isArray(d.metas)?d.metas:[],rows=[],seen=new Set(),event=meta.event;
  const terms=[...teamTokens(event.home||{}),...teamTokens(event.away||{})].filter(Boolean);
  const broadcasts=(event.broadcast||[]).map(norm).filter(Boolean);
  const push=(m,score,epg)=>{
    if(!m?.xtream?.streamUrl||seen.has(m.id)||score<35)return;
    seen.add(m.id);
    const title=decode(epg?.title||"");
    rows.push({name:\`▶ \${m.name}\`,url:m.xtream.streamUrl,title:m.name,description:\`\${m.xtream.category||"Live TV"} • match \${Math.min(100,Math.round(score))}%\${title?\` • \${title}\`:""}\`,score:Math.min(100,Math.round(score))});
    if(/\\.(ts|m3u8)$/i.test(m.xtream.streamUrl))rows.push({name:\`▶ \${m.name} • HLS\`,url:m.xtream.streamUrl.replace(/\\.ts$/i,".m3u8"),title:\`\${m.name} • HLS\`,description:"HLS alternate",score:Math.max(1,Math.round(score)-1)});
  };

  // Search every IPTV channel. Do not require a sports category.
  for(const m of all){
    const text=norm(\`\${m.name||""} \${m.xtream?.category||""}\`);let s=0;
    for(const t of terms)if(t&&text.includes(t))s=Math.max(s,t.length>=5?72:45);
    for(const b of broadcasts)if(b&&text.includes(b))s=100;
    if(meta.league==="ufc"&&/\\b(ufc|mma|fight|ppv|combat)\\b/i.test(text))s=Math.max(s,55);
    if(s)push(m,s,null);
  }

  // Search provider EPG for every channel concurrently.
  let cursor=0;const hits=[];
  const worker=async()=>{while(true){const n=cursor++;if(n>=all.length)return;const m=all[n],sid=m.xtream?.streamId;if(!sid||seen.has(m.id))continue;try{const epg=await getEpg(c,sid);let best=0,bestE=null;for(const e of epg||[]){const title=decode(e?.title||""),desc=decode(e?.description||""),txt=norm(\`\${title} \${desc}\`);let s=score(m,e,meta);for(const t of terms)if(t&&txt.includes(t))s=Math.max(s,t.length>=5?82:55);for(const b of broadcasts)if(b&&txt.includes(b))s=Math.max(s,88);if(e?.now_playing===1||e?.now_playing==="1")s+=10;if(s>best){best=s;bestE=e}}if(bestE)hits.push({m,score:best,e:bestE})}catch{}}};
  await Promise.race([Promise.all(Array.from({length:Math.min(24,Math.max(1,all.length))},worker)),new Promise(r=>setTimeout(r,12000))]);
  for(const h of hits.sort((a,b)=>b.score-a.score).slice(0,32))push(h.m,h.score,h.e);

  // Provider EPG may be incomplete. Return a small live-channel fallback so
  // a valid authorized stream is still exposed instead of an empty response.
  if(rows.length===0){
    const likely=all.filter(m=>m?.xtream?.streamUrl&&/\\b(live|main|event|game|channel|ppv|espn|fox|cbs|nbc|abc|tnt|usa|sports|nfl|nba|nhl|mlb|ufc|soccer)\\b/i.test(\`\${m.name} \${m.xtream?.category}\`));
    for(const m of likely.slice(0,24))push(m,36,null);
  }
  const value=rows.sort((a,b)=>(b.score||0)-(a.score||0)).slice(0,32);matchCache.set(key,{at:Date.now(),value});return value;
}
`;
    source = source.slice(0,start) + resolver + source.slice(next);
  }
}

fs.writeFileSync(file, source, "utf8");
console.log("[XSportsX] Universal stream resolver active: all channels + provider EPG + live fallback.");
