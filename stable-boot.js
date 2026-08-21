import fs from 'node:fs';
import { findPublicSportsSources, findConfiguredSources, MIN_SOURCES } from './source-finder.js';

const router = new URL('./sports-router.js', import.meta.url);
let s = fs.readFileSync(router, 'utf8');
const start = s.indexOf('async function streamsForEvent');
if (start < 0) throw new Error('streamsForEvent not found');
const nextCandidate = s.indexOf('async function ', start + 24);
const next = nextCandidate < 0 ? s.length : nextCandidate;

const resolver = String.raw`async function streamsForEvent(c,meta){
 if(!c||!meta?.event)return[];
 const key='sportio:'+c.server+'|'+c.username+'|'+meta.id+'|'+(c.sourceUrl||'');
 const cached=matchCache.get(key);if(cached&&Date.now()-cached.at<30000)return cached.value;
 const d=await xtreamData(c),all=Array.isArray(d.metas)?d.metas:[],e=meta.event;
 const home=teamTokens(e.home||{}),away=teamTokens(e.away||{}),broadcast=(e.broadcast||[]).map(norm).filter(Boolean);
 const rows=[],seen=new Set();
 const nameText=m=>norm([m?.name,m?.xtream?.category].filter(Boolean).join(' '));
 const has=(text,t)=>!!t&&text.includes(t);
 const teamHit=(text,tokens)=>tokens.some(x=>x&&has(text,x));
 const add=(m,score,p)=>{if(!m?.xtream?.streamUrl||seen.has(m.id)||score<45)return;seen.add(m.id);const title=decode(p?.title||''),desc=decode(p?.description||'');rows.push({name:'▶ '+m.name,url:m.xtream.streamUrl,title:m.name,description:(m.xtream.category||'Live TV')+' • '+Math.round(score)+'%'+(title?' • '+title:'')+(desc?' — '+desc.slice(0,220):''),behaviorHints:{isLive:true},score:Math.min(100,Math.round(score))});};
 const ranked=[];
 for(const m of all){const nt=nameText(m),h=teamHit(nt,home),a=teamHit(nt,away),b=broadcast.some(x=>has(nt,x));let score=h&&a?100:(b?78:(h||a?55:0));if(score)ranked.push({m,score});}
 const candidates=all.slice().sort((x,y)=>nameText(y).length-nameText(x).length).slice(0,180);let cursor=0;const hits=[];
 const worker=async()=>{while(true){const i=cursor++;if(i>=candidates.length)return;const m=candidates[i];try{const epg=await getEpg(c,m.xtream.streamId);for(const p of epg||[]){const title=norm(decode(p.title||'')),desc=norm(decode(p.description||'')),both=title+' '+desc,hn=teamHit(both,home),an=teamHit(both,away),bn=broadcast.some(x=>has(both,x));let score=0;if(hn&&an&&/\b(4k|uhd|2160p)\b/i.test(m.name+' '+p.title+' '+p.description))score=100;else if(teamHit(nameText(m),home)&&teamHit(nameText(m),away)&&hn&&an)score=96;else if(hn&&an)score=92;else if(bn&&(hn||an))score=78;else if(teamHit(nameText(m),home)||teamHit(nameText(m),away))score=58;if(p.now_playing===1||p.now_playing==='1')score+=8;const es=Date.parse(e.start||''),ps=Number(p.start_timestamp||0)*1000;if(es&&!Number.isNaN(es)&&ps){const delta=Math.abs(es-ps);if(delta<7200000)score+=12;else if(delta>43200000)score-=10;}if(score>=45)hits.push({m,score,p});}}catch{}}};
 await Promise.race([Promise.all(Array.from({length:Math.min(18,candidates.length||1)},worker)),new Promise(r=>setTimeout(r,9000))]);
 for(const r of ranked)if(r.score>=45)add(r.m,r.score,null);
 for(const h of hits.sort((a,b)=>b.score-a.score).slice(0,48))add(h.m,h.score,h.p);
 if(!rows.length)for(const r of ranked.sort((a,b)=>b.score-a.score).slice(0,16))add(r.m,r.score,null);
 if(c.sourceUrl&&rows.length<MIN_SOURCES){try{const found=await findConfiguredSources([c.sourceUrl],e);for(const f of found){if(!f?.url||seen.has(f.url))continue;seen.add(f.url);rows.push({name:'▶ Configured Web Source',url:f.url,title:f.url,description:'Configured source • '+f.latencyMs+'ms',behaviorHints:{isLive:true},score:Math.max(45,Math.min(90,100-Math.round(f.latencyMs/50)))});if(rows.length>=MIN_SOURCES)break;}}catch(err){console.warn('[XSportsX] configured Base64 source failed:',err?.message||err);}}
 if(rows.length<MIN_SOURCES){try{const found=await findPublicSportsSources(e);for(const f of found){if(!f?.url||seen.has(f.url))continue;seen.add(f.url);rows.push({name:'▶ Web Source',url:f.url,title:f.url,description:'Public web source • '+f.latencyMs+'ms',behaviorHints:{isLive:true},score:Math.max(45,Math.min(90,100-Math.round(f.latencyMs/50)))});if(rows.length>=MIN_SOURCES)break;}}catch(err){console.warn('[XSportsX] public source discovery failed:',err?.message||err);}}
 const value=rows.slice(0,48);matchCache.set(key,{at:Date.now(),value});return value;
}`;

s = s.slice(0,start) + resolver + '\n' + s.slice(next);
s = s.replace(
  "return v?.server&&v?.username&&v?.password?{server:String(v.server).replace(/\\/+$/,\"\"),username:String(v.username),password:String(v.password)}:null",
  "return v?.server&&v?.username&&v?.password?{server:String(v.server).replace(/\\/+$/,\"\"),username:String(v.username),password:String(v.password),sourceUrl:v.sourceUrl?String(v.sourceUrl):\"\"}:null"
);
fs.writeFileSync(router,s,'utf8');
console.log('[XSportsX] Sportio-style resolver + configured Base64 source URL + public source fallback installed.');
await import('./render-entry-v528.js');
