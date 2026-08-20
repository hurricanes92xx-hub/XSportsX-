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

// Resolve live events against ESPN's actual broadcast/network names first,
// then team names, then EPG title/description. This works even when the
// provider puts the game on a generic channel name rather than a sports group.
const start=source.indexOf("async function streamsForEvent");
const end=source.indexOf("async function ufcCatalog",start);
if(start>=0&&end>start){
 const resolver=`async function streamsForEvent(c,meta){
 if(!c||!meta?.event)return[];
 const key=\`fastmatch:\${c.server}|\${c.username}|\${meta.id}\`,cached=matchCache.get(key);
 if(cached&&Date.now()-cached.at<30000)return cached.value;
 const d=await xtreamData(c),all=Array.isArray(d.metas)?d.metas:[],e=meta.event,rows=[],seen=new Set();
 const home=teamTokens(e.home||{}),away=teamTokens(e.away||{});
 const broadcastNames=[...(e.broadcast||[]),...(e.networks||[]),...(e.channels||[])].map(norm).filter(x=>x.length>=2);
 const aliases={
  espn:["espn","espn hd","espn us","espnusa"],
  "espn2":["espn2","espn 2"],
  "espnu":["espnu","espn u"],
  "espnews":["espn news","espnews"],
  fs1:["fs1","fox sports 1","foxsports1"],
  fs2:["fs2","fox sports 2","foxsports2"],
  "fox sports":["fox sports","fox sports network"],
  "tnt sports":["tnt sports","tnt"],
  "nba tv":["nba tv","nbatv"],
  "mlb network":["mlb network","mlbn"],
  "nfl network":["nfl network","nfln"],
  "nhl network":["nhl network","nhln"],
  "cbs sports":["cbs sports","cbssn","cbs sports network"],
  "sec network":["sec network","secn"],
  "acc network":["acc network","accn"],
  "big ten network":["big ten network","btn"]
 };
 const networkTerms=new Set(broadcastNames);
 for(const b of broadcastNames)for(const a of (aliases[b]||[]))networkTerms.add(norm(a));
 const scoreText=(m,text,bonus=0)=>{
  const t=norm(text);let s=0;
  const h=home.some(x=>x&&t.includes(x)),a=away.some(x=>x&&t.includes(x));
  if(h&&a)s=100;else if(h||a)s=55;
  if([...networkTerms].some(x=>x&&t.includes(x)))s=Math.max(s,92);
  const league=norm(meta.league||"");
  if(league&&t.includes(league))s=Math.max(s,58);
  return Math.min(100,s+bonus);
 };
 const add=(m,s,p)=>{if(!m?.xtream?.streamUrl||seen.has(m.id)||s<25)return;seen.add(m.id);const pt=decode(p?.title||""),pd=decode(p?.description||"");rows.push({name:\`▶ \${m.name}\`,url:m.xtream.streamUrl,title:m.name,description:\`\${m.xtream.category||"Live TV"} • match \${Math.round(s)}%\${pt?\` • \${pt}\`:""}\${pd?\` — \${pd.slice(0,220)}\`:""}\`,behaviorHints:{isLive:true}})};
 // Pass 1: ESPN broadcast/network -> IPTV channel name/category.
 for(const m of all){const text=\`${m.name} \${m.xtream.category}\`;if([...networkTerms].some(x=>x&&norm(text).includes(x)))add(m,92,null)}
 // Pass 2: exact team/event names anywhere in the IPTV channel metadata.
 for(const m of all){const s=scoreText(m,\`${m.name} \${m.xtream.category}\`);if(s>=55)add(m,s,null)}
 // Pass 3: EPG title + description. Query only the remaining best candidates
 // so generic provider channel names do not make the request take forever.
 const candidates=all.filter(m=>!seen.has(m.id)).slice(0,96);let cursor=0;const hits=[];
 const worker=async()=>{while(true){const n=cursor++;if(n>=candidates.length)return;const m=candidates[n];try{const epg=await getEpg(c,m.xtream.streamId);for(const p of epg||[]){const s=scoreText(m,\`\${p.title||""} \${p.description||""}\`,p.now_playing===1||p.now_playing==="1"?15:0);if(s>=35)hits.push({m,s,p})}}catch{}}};
 await Promise.race([Promise.all(Array.from({length:Math.min(12,candidates.length||1)},worker)),new Promise(r=>setTimeout(r,6500))]);
 for(const h of hits.sort((a,b)=>b.s-a.s).slice(0,32))add(h.m,h.s,h.p);
 // If ESPN supplied a network but no exact match exists, return a small set
 // of live-capable channels rather than hanging or returning an invalid payload.
 if(!rows.length)for(const m of all.filter(x=>x?.xtream?.streamUrl).slice(0,8))add(m,25,null);
 const value=rows.slice(0,32);matchCache.set(key,{at:Date.now(),value});return value;
}
`;
 source=source.slice(0,start)+resolver+source.slice(end);
}

fs.writeFileSync(file,source,"utf8");
console.log("[XSportsX] boot patch applied: fixed recursive resolver + ESPN broadcast-first universal IPTV matcher");
