import fs from "node:fs";
const file=new URL("./sports-router.js",import.meta.url);let source=fs.readFileSync(file,"utf8");
source=source.replace('const i=p.indexOf(PREFIX);','const i=[PREFIX,"v527","v526","v528","v529","v530","v523"].map(x=>p.indexOf(x)).find(x=>x>=0);');
source=source.replace('async function resolveEventMeta(id){const h=await resolveEventMeta(id);if(h)return h;','async function resolveEventMeta(id){const cached=eventCache.get(id);if(cached)return cached;');
source=source.replace(/async function resolveEventMeta\(id\)\{\s*const h=await resolveEventMeta\(id\);\s*if\(h\)return h;/,'async function resolveEventMeta(id){const cached=eventCache.get(id);if(cached)return cached;');
const start=source.indexOf("async function streamsForEvent");
if(start>=0){const next=source.indexOf("async function ",start+20);if(next>start){const resolver=`async function streamsForEvent(c,meta){
 if(!c||!meta?.event)return[];const key=\`fast:\${c.server}|\${c.username}|\${meta.id}\`;const cached=matchCache.get(key);if(cached&&Date.now()-cached.at<20000)return cached.value;
 const d=await xtreamData(c),all=Array.isArray(d.metas)?d.metas:[],e=meta.event,rows=[],seen=new Set(),terms=[...teamTokens(e.home||{}),...teamTokens(e.away||{})].filter(Boolean),broadcasts=(e.broadcast||[]).map(norm).filter(Boolean);
 const add=(m,s,p)=>{if(!m?.xtream?.streamUrl||seen.has(m.id)||s<25)return;seen.add(m.id);rows.push({name:\`▶ \${m.name}\`,url:m.xtream.streamUrl,title:m.name,description:\`\${m.xtream.category||"Live TV"} • match \${Math.min(100,Math.round(s))}%\${p?.title?\` • \${decode(p.title)}\`:""}\`,score:Math.min(100,Math.round(s))});};
 // Immediate pass across ALL channels; games may be on ordinary channels.
 for(const m of all){const t=norm(\`\${m.name||""} \${m.xtream?.category||""}\`);let s=0;for(const x of terms)if(x&&t.includes(x))s=Math.max(s,x.length>=5?80:50);for(const b of broadcasts)if(b&&t.includes(b))s=100;if(meta.league==="ufc"&&/\\b(ufc|mma|fight|ppv|combat)\\b/i.test(t))s=Math.max(s,55);if(s)add(m,s,null);}
 // Fast EPG pass: only 120 best non-name matches, 16 concurrent workers, 6.5s cap.
 const candidates=all.filter(m=>!seen.has(m.id)).sort((a,b)=>{const aa=norm(\`\${a.name} \${a.xtream?.category}\`),bb=norm(\`\${b.name} \${b.xtream?.category}\`);const f=t=>terms.reduce((n,x)=>n+(x&&t.includes(x)?x.length:0),0)+broadcasts.reduce((n,x)=>n+(x&&t.includes(x)?x.length:0),0);return f(bb)-f(aa)}).slice(0,120);let i=0;const hits=[];const worker=async()=>{while(true){const n=i++;if(n>=candidates.length)return;const m=candidates[n];try{const epg=await getEpg(c,m.xtream.streamId);let best=0,bp=null;for(const p of epg||[]){const txt=norm(\`\${decode(p.title||"")} \${decode(p.description||"")}\`);let s=score(m,p,meta);for(const x of terms)if(x&&txt.includes(x))s=Math.max(s,x.length>=5?90:60);if(p.now_playing===1||p.now_playing==="1")s+=15;if(s>best){best=s;bp=p;}}if(bp)hits.push({m,s:best,p:bp});}catch{}}};await Promise.race([Promise.all(Array.from({length:Math.min(16,Math.max(1,candidates.length))},worker)),new Promise(r=>setTimeout(r,6500))]);for(const h of hits.sort((a,b)=>b.s-a.s).slice(0,32))add(h.m,h.s,h.p);
 // Never make Nuvio wait for a second long EPG sweep. Return immediate authorized candidates if EPG has no match.
 if(!rows.length)for(const m of all.filter(x=>x?.xtream?.streamUrl).slice(0,12))add(m,25,null);
 const value=rows.sort((a,b)=>(b.score||0)-(a.score||0)).slice(0,32);matchCache.set(key,{at:Date.now(),value});return value;
}
`;source=source.slice(0,start)+resolver+source.slice(next);}}
fs.writeFileSync(file,source,"utf8");console.log("[XSportsX] fast universal source resolver active");
