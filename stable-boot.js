import fs from 'node:fs';

const router = new URL('./sports-router.js', import.meta.url);
let s = fs.readFileSync(router, 'utf8');

// Replace only the source resolver. The gateway/catalog process remains untouched.
const start = s.indexOf('async function streamsForEvent');
if (start < 0) throw new Error('streamsForEvent not found');
const next = s.indexOf('async function ', start + 24);
if (next < 0) throw new Error('streamsForEvent boundary not found');

const resolver = String.raw`async function streamsForEvent(c,meta){
 if(!c||!meta?.event)return[];
 const key='sportio:'+c.server+'|'+c.username+'|'+meta.id;
 const cached=matchCache.get(key);if(cached&&Date.now()-cached.at<30000)return cached.value;
 const d=await xtreamData(c),all=Array.isArray(d.metas)?d.metas:[],e=meta.event;
 const home=teamTokens(e.home||{}),away=teamTokens(e.away||{}),broadcast=(e.broadcast||[]).map(norm).filter(Boolean);
 const rows=[],seen=new Set();
 const textFor=(m,p)=>norm([m?.name,m?.xtream?.category,p?.title?decode(p.title):'',p?.description?decode(p.description):''].filter(Boolean).join(' '));
 const nameText=m=>norm([m?.name,m?.xtream?.category].filter(Boolean).join(' '));
 const has=(text,t)=>!!t&&text.includes(t);
 const teamHit=(text,tokens)=>tokens.some(x=>x&&has(text,x));
 const add=(m,score,p)=>{if(!m?.xtream?.streamUrl||seen.has(m.id)||score<45)return;seen.add(m.id);const title=decode(p?.title||'');const desc=decode(p?.description||'');rows.push({name:'▶ '+m.name,url:m.xtream.streamUrl,title:m.name,description:(m.xtream.category||'Live TV')+' • '+Math.round(score)+'%'+(title?' • '+title:'')+(desc?' — '+desc.slice(0,220):''),behaviorHints:{isLive:true},score:Math.min(100,Math.round(score))});};
 const ranked=[];
 // Sportio-style tiers: channel name/category first, then EPG title/description.
 for(const m of all){
  const nt=nameText(m);let h=teamHit(nt,home),a=teamHit(nt,away),b=broadcast.some(x=>has(nt,x));
  let score=0;if(h&&a)score=100;else if(b)score=78;else if(h||a)score=55;
  if(score)ranked.push({m,score,epg:null});
 }
 // Every channel is eligible for EPG lookup. Prioritize likely candidates but do not filter the provider inventory by sports category.
 const candidates=all.slice().sort((x,y)=>(nameText(y).length-nameText(x).length)).slice(0,180);
 let cursor=0;const hits=[];
 const worker=async()=>{while(true){const i=cursor++;if(i>=candidates.length)return;const m=candidates[i];try{const epg=await getEpg(c,m.xtream.streamId);for(const p of epg||[]){const title=norm(decode(p.title||'')),desc=norm(decode(p.description||'')),both=title+' '+desc,hn=teamHit(both,home),an=teamHit(both,away),bn=broadcast.some(x=>has(both,x));let score=0;
   // Tier 1: both teams confirmed plus 4K marker.
   if(hn&&an&&/\b(4k|uhd|2160p)\b/i.test(m.name+' '+p.title+' '+p.description))score=100;
   // Tier 2: both teams in channel name and EPG description/title.
   else if(teamHit(nameText(m),home)&&teamHit(nameText(m),away)&&hn&&an)score=96;
   // Tier 3: both teams somewhere in title/description/name combined.
   else if(hn&&an)score=92;
   // Broadcast is strong evidence, but a conflicting explicit team should not win.
   else if(bn&&(hn||an))score=78;
   // Tier 4: one real team nickname in channel name, never city-only.
   else if(teamHit(nameText(m),home)||teamHit(nameText(m),away))score=58;
   if(p.now_playing===1||p.now_playing==='1')score+=8;
   const es=Date.parse(e.start||''),ps=Number(p.start_timestamp||0)*1000;if(es&&!Number.isNaN(es)&&ps){const delta=Math.abs(es-ps);if(delta<7200000)score+=12;else if(delta>43200000)score-=10;}
   if(score>=45)hits.push({m,score,p});
  }}catch{}}};
 await Promise.race([Promise.all(Array.from({length:Math.min(18,candidates.length||1)},worker)),new Promise(r=>setTimeout(r,9000))]);
 for(const r of ranked)if(r.score>=45)add(r.m,r.score,r.epg);
 for(const h of hits.sort((a,b)=>b.score-a.score).slice(0,48))add(h.m,h.score,h.p);
 // If provider EPG is missing, return strong channel/broadcast candidates rather than an empty result.
 if(!rows.length)for(const r of ranked.sort((a,b)=>b.score-a.score).slice(0,16))add(r.m,r.score,null);
 const value=rows.slice(0,48);matchCache.set(key,{at:Date.now(),value});return value;
}`;

s=s.slice(0,start)+resolver+'\n';
fs.writeFileSync(router,s,'utf8');
console.log('[XSportsX] Sportio-style resolver installed; all IPTV channels eligible, ESPN broadcast + team + EPG title/description tiers enabled.');

await import('./render-entry-v528.js');
