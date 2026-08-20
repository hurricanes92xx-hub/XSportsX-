import fs from "node:fs";

const file = new URL("./sports-router.js", import.meta.url);
let source = fs.readFileSync(file, "utf8");

const broken = 'async function resolveEventMeta(id){const h=await resolveEventMeta(id);if(h)return h;';
const fixed = 'async function resolveEventMeta(id){const cached=eventCache.get(id);if(cached)return cached;';

if (source.includes(broken)) {
  source = source.replace(broken, fixed);
  console.log("[XSportsX] Fixed recursive resolveEventMeta() before backend start.");
}

source = source.replace(
  /async function resolveEventMeta\(id\)\{\s*const h=await resolveEventMeta\(id\);\s*if\(h\)return h;/,
  'async function resolveEventMeta(id){const cached=eventCache.get(id);if(cached)return cached;'
);

// Bound the original EPG fallback so it cannot stall Nuvio indefinitely.
source = source.replace(').slice(0,500);', ').slice(0,24);');
source = source.replace('u.toString(),5000)', 'u.toString(),1800)');
source = source.replace('f.toString(),5000)', 'f.toString(),1800)');
source = source.replace('set("limit","20")', 'set("limit","10")');

// Replace the fragile source matcher with a deterministic Xtream matcher.
// It first scores cheap channel-name/category matches, then checks EPG only
// for the best candidates. This prevents "Finding streams" hangs and avoids
// requiring the provider's channel title to exactly match the ESPN event title.
source += `\n\nasync function streamsForEvent(c,meta){
  if(!c||!meta?.event)return[];
  const k=\`match-v2:\${c.server}|\${c.username}|\${meta.id}\`,h=matchCache.get(k);
  if(h&&Date.now()-h.at<30000)return h.value;
  const d=await xtreamData(c), e=meta.event, all=Array.isArray(d.metas)?d.metas:[], now=Date.now();
  const sportRe=/\\b(sport|sports|espn|fox|fs1|fs2|tnt|nba|mlb|nhl|nfl|ncaaf|sec|acc|big ten|bally|msg|regional|baseball|basketball|football|hockey|soccer|tennis|golf|cbs sports|nbc sports|league pass|game|event|ppv)\\b/i;
  const home=teamTokens(e.home||{}), away=teamTokens(e.away||{}), pair=[...home,...away];
  const broadcast=(e.broadcast||[]).map(norm).filter(Boolean);
  const cheap=(m)=>{const t=norm(\`\${m.name} \${m.xtream?.category||\"\"}\`);let s=0;
    for(const x of home)if(x&&t.includes(x))s+=x.length>=5?42:24;
    for(const x of away)if(x&&t.includes(x))s+=x.length>=5?42:24;
    for(const b of broadcast)if(b&&t.includes(b))s+=55;
    if(sportRe.test(t))s+=10;
    if(meta.league==='ufc'&&/\\b(ufc|mma|fight|ppv|combat)\\b/i.test(t))s+=55;
    if(meta.league!=='ufc'&&/\\b(ufc|mma|fight pass)\\b/i.test(t)&&!sportRe.test(t))s-=30;
    return s;};
  let candidates=all.map(m=>({m,s:cheap(m)})).filter(x=>x.s>0).sort((a,b)=>b.s-a.s).slice(0,48);
  if(!candidates.length)candidates=all.filter(m=>sportRe.test(\`\${m.name} \${m.xtream?.category||\"\"}\`)).slice(0,24).map(m=>({m,s:5}));
  const scored=[];let p=0;
  const worker=async()=>{while(p<candidates.length){const x=candidates[p++],m=x.m,sid=m.xtream?.streamId;if(!sid)continue;let best=x.s,be=null;
    try{const epg=await getEpg(c,sid);for(const item of epg||[]){const es=score(m,item,meta);if(es>best){best=es;be=item;}}}catch{}
    const live=be&&(be.now_playing===1||be.now_playing==='1');
    const starts=be?.start_timestamp?Number(be.start_timestamp)*1000:0;
    if(starts&&Math.abs(starts-now)>18*60*60*1000&&best<75)continue;
    if(best>=18)add(scored, new Set(), m, Math.min(100,best), be);
  }};
  await Promise.all(Array.from({length:Math.min(8,candidates.length||1)},()=>worker()));
  const seen=new Set(),rows=[];
  for(const r of scored.sort((a,b)=>(b.score||0)-(a.score||0))){if(seen.has(r.url))continue;seen.add(r.url);rows.push(r);if(rows.length>=12)break;}
  // For a live event, return the best sports-channel candidates even when the
  // provider has no usable EPG. A generic channel must never be the only result
  // unless it is explicitly categorized as sports by the provider.
  if(!rows.length&&e.state==='in'){
    for(const x of candidates.slice(0,8)){
      if(x.s<10)continue;const m=x.m;
      if(!sportRe.test(\`\${m.name} \${m.xtream?.category||\"\"}\`))continue;
      add(rows,seen,m,Math.max(18,x.s),null);
      if(rows.length>=8)break;
    }
  }
  const value=rows.slice(0,16);matchCache.set(k,{at:Date.now(),value});return value;
}
`;

fs.writeFileSync(file, source, "utf8");
console.log("[XSportsX] Startup patch applied: metadata recursion fixed, EPG bounded, and resilient Xtream event source matching enabled.");
`;
