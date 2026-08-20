import fs from "node:fs";

const file = new URL("./sports-router.js", import.meta.url);
let source = fs.readFileSync(file, "utf8");

const broken = 'async function resolveEventMeta(id){const h=await resolveEventMeta(id);if(h)return h;';
const fixed = 'async function resolveEventMeta(id){const cached=eventCache.get(id);if(cached)return cached;';

if (source.includes(broken)) source = source.replace(broken, fixed);
source = source.replace(/async function resolveEventMeta\(id\)\{\s*const h=await resolveEventMeta\(id\);\s*if\(h\)return h;/,'async function resolveEventMeta(id){const cached=eventCache.get(id);if(cached)return cached;');
source = source.replace(').slice(0,500);', ').slice(0,24);');
source = source.replace('u.toString(),5000)', 'u.toString(),1800)');
source = source.replace('f.toString(),5000)', 'f.toString(),1800)');
source = source.replace('set("limit","20")', 'set("limit","10")');

// Rename the original resolver before installing the universal resolver. The
// router already defines streamsForEvent(); redeclaring it causes Node to exit
// with status 1 during module loading.
source = source.replace('async function streamsForEvent(c,meta){', 'async function streamsForEventLegacy(c,meta){');

// Universal source resolver. Sports broadcasts can be carried on ordinary
// entertainment, local, news, or numbered channels. Never filter the provider
// inventory by channel/category name before checking the provider's EPG.
source += `\n\nconst xsXmltvCache=new Map();
async function xsGetText(url,timeout=7000){const ac=new AbortController(),tm=setTimeout(()=>ac.abort(),timeout);try{const r=await fetch(url,{signal:ac.signal,headers:{accept:'application/xml,text/xml,text/plain','user-agent':\`XSportsX/\${VERSION}\`}});if(!r.ok)throw new Error('HTTP '+r.status);return await r.text()}finally{clearTimeout(tm)}}
function xsXml(s){return String(s||'').replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&#39;/g,"'").replace(/&quot;/g,'"').replace(/&#(\\d+);/g,(_,n)=>String.fromCharCode(Number(n)))}
async function xsXmltv(c){const k=\`xmltv:\${c.server}|\${c.username}\`,h=xsXmltvCache.get(k);if(h&&Date.now()-h.at<120000)return h.value;try{const u=new URL('/xmltv.php',c.server);u.searchParams.set('username',c.username);u.searchParams.set('password',c.password);const text=await xsGetText(u.toString(),6500);if(!text||!/<(?:tv|programme)\\b/i.test(text))return[];const rows=[];const re=/<programme\\b([^>]*)>([\\s\\S]*?)<\\/programme>/gi;let m;while((m=re.exec(text))&&rows.length<5000){const attrs=m[1],body=m[2],chan=(attrs.match(/\\bchannel=["']([^"']+)["']/i)||[])[1]||'',start=(attrs.match(/\\bstart=["']([^"']+)["']/i)||[])[1]||'',stop=(attrs.match(/\\bstop=["']([^"']+)["']/i)||[])[1]||'',title=xsXml((body.match(/<title(?:\\s[^>]*)?>([\\s\\S]*?)<\\/title>/i)||[])[1]||''),desc=xsXml((body.match(/<desc(?:\\s[^>]*)?>([\\s\\S]*?)<\\/desc>/i)||[])[1]||'');if(chan&&title)rows.push({channel:chan,start,stop,title,description:desc,now_playing:Date.parse(start)<=Date.now()&&(!stop||Date.parse(stop)>=Date.now())?1:0})}xsXmltvCache.set(k,{at:Date.now(),value:rows});return rows}catch{return h?.value||[]}}
function xsEventMatch(text,meta){const t=norm(text),e=meta?.event||{},home=teamTokens(e.home||{}),away=teamTokens(e.away||{});let hs=0,as=0;for(const x of home)if(x&&t.includes(x))hs=Math.max(hs,x.length>=5?1:.65);for(const x of away)if(x&&t.includes(x))as=Math.max(as,x.length>=5?1:.65);if(meta.league==='ufc'&&/\\b(ufc|mma|fight|fight night|ppv|combat)\\b/i.test(t))return Math.max(70,(hs+as)*45);return hs&&as?Math.min(100,70+(hs+as)*15):Math.max(hs,as)*55}
async function streamsForEvent(c,meta){
  if(!c||!meta?.event)return[];
  const k=\`universal-match:\${c.server}|\${c.username}|\${meta.id}\`,cached=matchCache.get(k);if(cached&&Date.now()-cached.at<30000)return cached.value;
  const d=await xtreamData(c),all=Array.isArray(d.metas)?d.metas:[],rows=[],seen=new Set(),event=meta.event;
  const addOne=(m,s,e)=>{if(!m?.xtream?.streamUrl||seen.has(m.id)||s<45)return;add(rows,seen,m,Math.min(100,Math.round(s)),e)};
  // 1) Cheap scan of EVERY channel name/category. No sports-category filter.
  for(const m of all){const t=norm(\`\${m.name} \${m.xtream?.category||''}\`);let s=0;for(const x of [...teamTokens(event.home||{}),...teamTokens(event.away||{})])if(x&&t.includes(x))s+=x.length>=5?52:32;for(const b of (event.broadcast||[]))if(norm(b)&&t.includes(norm(b)))s=100;if(meta.league==='ufc'&&/\\b(ufc|mma|fight|ppv|combat)\\b/i.test(t))s+=40;if(s>=45)addOne(m,s,null)}
  // 2) Provider-wide XMLTV. This catches games carried on ordinary channel names.
  const xml=await xsXmltv(c);if(xml.length){const byChan=new Map();for(const p of xml){const a=byChan.get(p.channel)||[];a.push(p);byChan.set(p.channel,a)}for(const m of all){const ids=[m.xtream?.epgChannelId,m.name].filter(Boolean).map(norm);for(const [cid,programs] of byChan){const nc=norm(cid);if(!ids.some(x=>x&&(nc===x||nc.includes(x)||x.includes(nc))))continue;let best=0,bestE=null;for(const p of programs){const s=xsEventMatch(\`\${p.title} \${p.description}\`,meta);if(s>best){best=s;bestE=p}}if(best>=45)addOne(m,best,bestE)}}}
  // 3) If XMLTV is absent or IDs don't line up, query short EPG across the
  // ENTIRE live inventory in parallel. Ordinary channels are intentionally included.
  let idx=0;const hits=[];const worker=async()=>{while(true){const n=idx++;if(n>=all.length)return;const m=all[n],sid=m.xtream?.streamId;if(!sid)continue;try{const epg=await getEpg(c,sid);let best=0,be=null;for(const p of epg||[]){const a=score(m,p,meta),b=xsEventMatch(\`\${p.title||''} \${p.description||''}\`,meta),s=Math.max(a,b);if(s>best){best=s;be=p}}if(best>=45)hits.push({m,best,be})}catch{}}};
  const workers=Array.from({length:Math.min(24,Math.max(1,all.length))},worker);await Promise.race([Promise.all(workers),new Promise(r=>setTimeout(r,8000))]);
  for(const x of hits.sort((a,b)=>b.best-a.best).slice(0,24))addOne(x.m,x.best,x.be);
  const value=rows.sort((a,b)=>(b.score||0)-(a.score||0)).slice(0,16);matchCache.set(k,{at:Date.now(),value});return value;
}
`;

fs.writeFileSync(file, source, "utf8");
console.log("[XSportsX] Universal source matcher enabled: all IPTV channels, provider-wide XMLTV, channel-wide EPG, team/broadcast matching.");
