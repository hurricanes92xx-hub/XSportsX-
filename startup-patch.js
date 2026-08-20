import fs from "node:fs";

const file = new URL("./sports-router.js", import.meta.url);
let source = fs.readFileSync(file, "utf8");

// Accept every known gateway prefix and locate the encrypted config token anywhere after it.
source = source.replace(
  'const i=p.indexOf(PREFIX);',
  'const i=[PREFIX,"v527","v526","v528","v529","v530","v523"].map(x=>p.indexOf(x)).find(x=>x>=0);'
);
source = source.replace(
  "if(i>=0&&p[i+1]&&!['manifest.json','configure','health'].includes(p[i+1]))return decryptConfig(decodeURIComponent(p[i+1]));",
  'if(i>=0){for(let j=i+1;j<p.length;j++){if(!["manifest.json","configure","health","catalog","meta","stream"].includes(p[j])){const cfg=decryptConfig(decodeURIComponent(p[j]));if(cfg)return cfg}}}'
);

// The previous router contained a self-recursive resolver. Replace it with the cached lookup.
source = source.replace(
  /async function resolveEventMeta\(id\)\{\s*const h=await resolveEventMeta\(id\);\s*if\(h\)return h;/,
  'async function resolveEventMeta(id){const cached=eventCache.get(id);if(cached)return cached;'
);

// Universal live-event resolver: channel name first, then EPG title + description across ALL channels.
const start = source.indexOf("async function streamsForEvent");
if (start >= 0) {
  const next = source.indexOf("async function ", start + 20);
  if (next > start) {
    const resolver = [
      'async function streamsForEvent(c,meta){',
      'if(!c||!meta?.event)return[];',
      'const key="name-epg:"+c.server+"|"+c.username+"|"+meta.id;',
      'const cached=matchCache.get(key);if(cached&&Date.now()-cached.at<30000)return cached.value;',
      'const d=await xtreamData(c),all=Array.isArray(d.metas)?d.metas:[],e=meta.event,rows=[],seen=new Set();',
      'const home=teamTokens(e.home||{}),away=teamTokens(e.away||{}),broadcasts=(e.broadcast||[]).map(norm).filter(Boolean);',
      'const cleanText=v=>norm(decode(v||""));',
      'const add=(m,s,p)=>{if(!m?.xtream?.streamUrl||seen.has(m.id)||s<20)return;seen.add(m.id);const pt=decode(p?.title||""),pd=decode(p?.description||"");rows.push({name:"▶ "+m.name,url:m.xtream.streamUrl,title:m.name,description:(m.xtream.category||"Live TV")+" • match "+Math.min(100,Math.round(s))+((pt)?" • "+pt:"")+((pd)?" — "+pd.slice(0,180):""),score:Math.min(100,Math.round(s))});};',
      'const nameScore=m=>{const t=norm((m.name||"")+" "+(m.xtream?.category||""));let hs=0,as=0;for(const x of home)if(x&&t.includes(x))hs=Math.max(hs,x.length>=5?80:50);for(const x of away)if(x&&t.includes(x))as=Math.max(as,x.length>=5?80:50);let s=hs&&as?100:Math.max(hs,as);for(const b of broadcasts)if(b&&t.includes(b))s=100;if(meta.league==="ufc"&&/\\b(ufc|mma|fight|ppv|combat)\\b/i.test(t))s=Math.max(s,60);return s};',
      'for(const m of all){const s=nameScore(m);if(s)add(m,s,null);}',
      'const remaining=all.filter(m=>!seen.has(m.id));let cursor=0;const hits=[];',
      'const worker=async()=>{while(true){const n=cursor++;if(n>=remaining.length)return;const m=remaining[n];try{const epg=await getEpg(c,m.xtream.streamId);for(const p of epg||[]){const title=cleanText(p.title),desc=cleanText(p.description);let hs=0,as=0;for(const x of home)if(title.includes(x)||desc.includes(x))hs=Math.max(hs,x.length>=5?80:50);for(const x of away)if(title.includes(x)||desc.includes(x))as=Math.max(as,x.length>=5?80:50);let s=hs&&as?100:Math.max(hs,as);for(const b of broadcasts)if(title.includes(b)||desc.includes(b)||cleanText(m.name).includes(b))s=Math.max(s,88);if(p.now_playing===1||p.now_playing==="1")s+=15;const ts=Number(p.start_timestamp||0)*1000,es=Date.parse(e.start||"");if(ts&&es){const delta=Math.abs(ts-es);if(delta<7200000)s+=18;else if(delta<21600000)s+=8;}if(s>=35)hits.push({m:m,s:s,p:p});}}catch{}}};',
      'await Promise.race([Promise.all(Array.from({length:Math.min(32,Math.max(1,remaining.length))},worker)),new Promise(r=>setTimeout(r,15000))]);',
      'for(const h of hits.sort((a,b)=>b.s-a.s).slice(0,64))add(h.m,h.s,h.p);',
      'if(!rows.length)for(const m of all.filter(x=>x?.xtream?.streamUrl).slice(0,24))add(m,20,null);',
      'const value=rows.sort((a,b)=>(b.score||0)-(a.score||0)).slice(0,64);matchCache.set(key,{at:Date.now(),value});return value;',
      '}'
    ].join("\n");
    source = source.slice(0, start) + resolver + source.slice(next);
  }
}

fs.writeFileSync(file, source, "utf8");
console.log("[XSportsX] universal event-name + EPG-title/description matcher active");
