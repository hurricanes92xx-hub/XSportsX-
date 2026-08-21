const fs = require('node:fs');
const path = require('node:path');

const file = path.join(process.cwd(), 'server.js');
let src = fs.readFileSync(file, 'utf8');
const version = '20260821-13';

// Keep the stable server baseline, but make UFC catalog entries event-level.
const oldUfc = "async function ufcEvents(req,data){const out=[];for(const e of data?.events||[]){const comps=e.competitions||[];for(const c of comps){const cs=c.competitors||[];if(cs.length<2)continue;const away=athleteInfo(cs.find(x=>x.homeAway==='away')||cs[0]),home=athleteInfo(cs.find(x=>x.homeAway==='home')||cs[1]);if(away.name==='TBD'&&home.name==='TBD')continue;const state=c.status?.type?.state||e.status?.type?.state||'pre',id=`${e.id}-${c.id||Math.random().toString(36).slice(2)}`,event={id:String(id),league:'ufc',start:c.date||e.date||'',state,home,away,broadcast:(c.broadcasts||e.broadcasts||[]).flatMap(x=>x.names||[])};const detail=c.status?.type?.shortDetail||e.status?.type?.shortDetail||e.name||'Fight scheduled';const meta=safeMeta(req,'ufc',{id:`sport:ufc:${event.id}`,type:'tv',name:`${away.name} vs ${home.name}`,poster:eventArtworkUrl(req,event),background:eventArtworkUrl(req,event),description:`UFC • ${detail}\\n${event.start||''}`,releaseInfo:event.start||e.date||'',genres:['Sports','UFC'],sportSource:'ufc',eventId:event.id,event,posterShape:'landscape'});eventCache.set(meta.id,meta);out.push(meta)}}return out}";
const newUfc = "async function ufcEvents(req,data){const out=[];for(const e of data?.events||[]){const c=(e.competitions||[]).find(x=>(x.competitors||[]).length>=2)||(e.competitions||[])[0];const cs=c?.competitors||[];const away=athleteInfo(cs.find(x=>x.homeAway==='away')||cs[0]||{}),home=athleteInfo(cs.find(x=>x.homeAway==='home')||cs[1]||{});const state=c?.status?.type?.state||e.status?.type?.state||'pre';const event={id:String(e.id),league:'ufc',name:e.name||'UFC Fight Night',start:c?.date||e.date||'',state,home,away,broadcast:(c?.broadcasts||e.broadcasts||[]).flatMap(x=>x.names||[])};const meta=safeMeta(req,'ufc',{id:`sport:ufc:${event.id}`,type:'tv',name:event.name,poster:eventArtworkUrl(req,event),background:eventArtworkUrl(req,event),description:`UFC • ${c?.status?.type?.shortDetail||e.status?.type?.shortDetail||'Fight Night'}\\n${event.start||e.date||''}`,releaseInfo:event.start||e.date||'',genres:['Sports','UFC'],sportSource:'ufc',eventId:event.id,event,posterShape:'landscape'});eventCache.set(meta.id,meta);out.push(meta)}return out}";
if(src.includes(oldUfc)) src=src.replace(oldUfc,newUfc); else console.log('cache-bust: UFC function already patched or baseline changed');

// Version the generated artwork so Nuvio cannot reuse old blank posters.
src = src.replace(/function eventArtworkUrl\(req,e\)\{return `\$\{baseUrl\(req\)}\/artwork\/event-v8\/\$\{encodeURIComponent\(e\.league\)\}\/\$\{encodeURIComponent\(e\.id\)\}\.png\?v=9`\}/,
  "function eventArtworkUrl(req,e){return `${baseUrl(req)}/artwork/event-v8/${encodeURIComponent(e.league)}/${encodeURIComponent(e.id)}.png?v=13`}");

// Pass the UFC event title to the artwork renderer; normal games stay matchup cards.
src = src.replace(
  "eventArtworkUrl(req,event),background:eventArtworkUrl(req,event),description:`UFC •",
  "eventArtworkUrl(req,event),background:eventArtworkUrl(req,event),description:`UFC •"
);

src = src.replace("const e=m.event,[a,h]=await Promise.all([fetchLogoData(e.away.logo),fetchLogoData(e.home.logo)]),svg=eventArtworkSvg(e.league,e.away.name,e.home.name,e.state,e.start,a,h,e.away.short,e.home.short)","const e=m.event,[a,h]=await Promise.all([fetchLogoData(e.away.logo),fetchLogoData(e.home.logo)]),svg=eventArtworkSvg(e.league,e.away.name,e.home.name,e.state,e.start,a,h,e.away.short,e.home.short,e.name||'')");

src = src.replace(
  ".png().toBuffer();res.type('image/png')",
  ".png({compressionLevel:9,quality:84}).toBuffer();res.type('image/png')"
);

src = src.replace(
  "res.type('image/png').set('Cache-Control','public, max-age=300').set('X-XSportsX-Art','raster-v2').send(png)",
  "res.type('image/png').set('Cache-Control','no-store, max-age=0').set('X-XSportsX-Art',version).send(png)"
);

// MLB catalog safety net: prefer MLB StatsAPI, then fall back to the existing ESPN feed.
// This keeps MLB and Live Now independent from an ESPN scoreboard outage.
if(!src.includes('MLB catalog safety net')){
  const marker='const CATALOGS=[';
  const patch=`// MLB catalog safety net: prefer MLB StatsAPI, then fall back to the existing ESPN feed.\n// This keeps MLB and Live Now independent from an ESPN scoreboard outage.\nasync function mlbStatsEvents(req){\n  return cached(\`mlb:stats:\${dateRange()}\`,SCORE_TTL,async()=>{\n    const now=new Date(),from=new Date(now),to=new Date(now);\n    from.setUTCDate(from.getUTCDate()-1);to.setUTCDate(to.getUTCDate()+3);\n    const iso=d=>d.toISOString().slice(0,10);\n    try{\n      const r=await axios.get('https://statsapi.mlb.com/api/v1/schedule',{timeout:12000,headers:{'User-Agent':'XSportsX/3.1','Accept':'application/json'},params:{sportId:1,startDate:iso(from),endDate:iso(to),hydrate:'team,linescore'}});\n      const out=[];\n      for(const day of r.data?.dates||[]){\n        for(const g of day.games||[]){\n          const h=g.teams?.home||{},a=g.teams?.away||{},ht=h.team||{},at=a.team||{};\n          if(!ht.name&&!at.name)continue;\n          const st=g.status||{};\n          const state=st.abstractGameState==='Live'||st.codedGameState==='I'?'in':(st.abstractGameState==='Final'||st.codedGameState==='F'?'post':'pre');\n          const logo=t=>t?.id?\`https://www.mlbstatic.com/team-logos/\${t.id}.svg\`:'';\n          const event={id:String(g.gamePk),league:'mlb',start:g.gameDate||'',state,home:{name:ht.name||'',short:ht.abbreviation||ht.name?.slice(0,4)||'',logo:logo(ht)},away:{name:at.name||'',short:at.abbreviation||at.name?.slice(0,4)||'',logo:logo(at)},broadcast:(g.broadcasts||[]).flatMap(x=>x.name?[x.name]:[]).filter(Boolean)};\n          const detail=st.detailedState||st.abstractGameState||'Scheduled';\n          const m=safeMeta(req,'mlb',{id:\`sport:mlb:\${event.id}\`,type:'tv',name:\`\${event.away.name} vs \${event.home.name}\`,poster:eventArtworkUrl(req,event),background:eventArtworkUrl(req,event),description:\`MLB • \${detail}\\n\${event.start||''}\`,releaseInfo:event.start||'',genres:['Sports','MLB'],sportSource:'mlb',eventId:event.id,event,behaviorHints:{isPlayable:true}});\n          eventCache.set(m.id,m);eventCache.set(\`sport:mlb:\${event.id}\`,m);out.push(m);\n        }\n      }\n      return out;\n    }catch(err){console.error('[mlb-stats]',err.message);return[]}\n  });\n}\nconst xsOriginalLeagueEvents=leagueEvents;\nleagueEvents=async function(k,req){\n  if(k==='mlb'){\n    const primary=await mlbStatsEvents(req);\n    if(primary.length)return primary;\n  }\n  return xsOriginalLeagueEvents(k,req);\n};\n`;
  if(src.includes(marker)) src=src.replace(marker,patch+marker); else console.log('cache-bust: CATALOGS marker not found; MLB safety net not injected');
}

fs.writeFileSync(file, src);
console.log(`cache-bust: XSportsX artwork ${version}; UFC is event-level; MLB uses StatsAPI safety net`);
