import fs from "node:fs";

const path = new URL("./sports-router.js", import.meta.url);
let s = fs.readFileSync(path, "utf8");

const oldResolve = /async function resolveEventMeta\(id\)\{.*?\n\}function manifest/s;
const newResolve = `async function resolveEventMeta(id){
 const cached=eventCache.get(id); if(cached)return cached;
 const raw=String(id).replace(/^sport:/,"");
 for(const l of Object.keys(LEAGUES)){
  try{
   const list=l==="ufc"?await ufcCatalog():await leagueCatalog(l);
   const found=list.find(x=>String(x.eventId)===raw||String(x.event?.id)===raw||String(x.id)===id);
   if(found){eventCache.set(id,found);return found}
  }catch{}
 }
 return null
}
function manifest`;
s=s.replace(oldResolve,newResolve);

const oldScore = /function score\(m,e,meta\)\{.*?\n\}function add/s;
const newScore = `function score(m,e,meta){
 const event=meta?.event||{}, epgTitle=decode(e?.title||""), epgDesc=decode(e?.description||""), channel=decode(m?.name||""), category=decode(m?.xtream?.category||"");
 const text=norm([channel,category,epgTitle,epgDesc].join(" "));
 const eventText=norm([meta?.name||"",event?.home?.name||"",event?.away?.name||"",event?.home?.short||"",event?.away?.short||"",...(event?.broadcast||[])].join(" "));
 const tokens=[...new Set(eventText.split(" ").filter(x=>x.length>=3))];
 let hits=0,weighted=0;
 for(const x of tokens){if(text.includes(x)){hits++;weighted+=x.length>=6?3:1}}
 let s=hits>=4?92:hits>=3?84:hits>=2?70:hits>=1?48:0;
 const aliases={nfl:["nfl","football"],ncaaf:["ncaaf","college football","ncaa"],nba:["nba","basketball"],nhl:["nhl","hockey"],mlb:["mlb","baseball"],soccer:["soccer","football"],ufc:["ufc","mma","fight night","fight pass"]}[String(meta?.league||"")]||[];
 if(aliases.some(x=>text.includes(norm(x))))s+=10;
 if(e?.now_playing===1||e?.now_playing==="1")s+=15;
 const es=Date.parse(event?.start||""), ts=Number(e?.start_timestamp||0)*1000;
 if(es&&!Number.isNaN(es)&&ts){const d=Math.abs(es-ts);if(d<30*60000)s+=22;else if(d<90*60000)s+=16;else if(d<3*3600000)s+=9;else if(d<12*3600000)s+=3}
 if(event?.broadcast?.some(b=>norm(b)&&text.includes(norm(b))))s+=10;
 if(epgTitle&&norm(meta?.name||"")&&text.includes(norm(meta.name)))s+=8;
 return Math.min(100,s+Math.min(8,weighted));
}
function add`;
s=s.replace(oldScore,newScore);

fs.writeFileSync(path,s);
console.log("XSportsX startup patch: fixed event metadata resolution + EPG/name matching");
