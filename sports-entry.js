const fs=require('fs');
const path=require('path');

const target=path.join(__dirname,'hotfix-entry.js');
let source=fs.readFileSync(target,'utf8');
const start=source.indexOf('const LEAGUES={');
const end=source.indexOf('\n};\nconst SPORT=',start);
if(start<0||end<0)throw new Error('Unable to locate hotfix LEAGUES registry');

const expanded=`const LEAGUES={
  nfl:['NFL','football','nfl','🏈'],ncaaf:['NCAA Football','football','college-football','🏈'],
  nba:['NBA','basketball','nba','🏀'],wnba:['WNBA','basketball','wnba','🏀'],ncaab:['NCAA Basketball','basketball','mens-college-basketball','🏀'],
  ncaav:['NCAA Volleyball','volleyball','womens-college-volleyball','🏐'],mlb:['MLB','baseball','mlb','⚾'],nhl:['NHL','hockey','nhl','🏒'],
  mls:['MLS','soccer','usa.1','⚽'],epl:['Premier League','soccer','eng.1','⚽'],ucl:['UEFA Champions League','soccer','uefa.champions','⚽'],
  laliga:['LaLiga','soccer','esp.1','⚽'],seriea:['Serie A','soccer','ita.1','⚽'],bundesliga:['Bundesliga','soccer','ger.1','⚽'],ligue1:['Ligue 1','soccer','fra.1','⚽'],
  ufc:['UFC','mma','ufc','🥊'],boxing:['Boxing','boxing','boxing','🥊'],
  f1:['Formula 1','racing','f1','🏎️'],nascar:['NASCAR Cup','racing','nascar-premier','🏁'],indycar:['IndyCar','racing','irl','🏎️'],
  motogp:['MotoGP','racing','motogp','🏍️'],wrc:['FIA World Rally Championship','rally','wrc','🏎️'],wec:['FIA World Endurance Championship','endurance','wec','🏎️'],
  imsa:['IMSA SportsCar Championship','endurance','imsa','🏎️'],formulae:['ABB FIA Formula E','racing','formula-e','⚡'],mxgp:['FIM Motocross World Championship','motocross','mxgp','🏍️'],
  monsterjam:['Monster Jam','monster-trucks','monsterjam','🚚'],rugby_six:['Six Nations Rugby','rugby','180659','🏉'],rugby_world:['Rugby World Cup','rugby','164205','🏉'],
  rugby_nrl:['NRL Rugby League','rugby-league','3','🏉'],lacrosse_pll:['Premier Lacrosse League','lacrosse','pll','🥍'],lacrosse_nll:['National Lacrosse League','lacrosse','nll','🥍'],
  volleyball_w:['NCAA Women’s Volleyball','volleyball','womens-college-volleyball','🏐'],volleyball_m:['NCAA Men’s Volleyball','volleyball','mens-college-volleyball','🏐'],
  afl:['Australian Football','australian-football','afl','🏉'],cricket_ipl:['IPL Cricket','cricket','ipl','🏏'],cricket_t20:['ICC T20 Cricket','cricket','icc.t20','🏏']
};`;
source=source.slice(0,start)+expanded+source.slice(end+3);

const officialSources={
  f1:'https://www.formula1.com/en/racing/2026',nascar:'https://www.nascar.com/nascar-cup-series/2026/schedule/',indycar:'https://www.indycar.com/Schedule',
  motogp:'https://www.motogp.com/en/Calendar',wrc:'https://www.wrc.com/en/',wec:'https://www.fiawec.com/en/',
  imsa:'https://www.imsa.com/weathertech/weathertech-2026-schedule/',formulae:'https://www.fiaformulae.com/en/calendar',mxgp:'https://www.mxgp.com/calendar',
  monsterjam:'https://www.monsterjam.com/en-us/tickets/',rugby_six:'https://www.world.rugby/tournaments/fixtures-results',rugby_world:'https://www.world.rugby/tournaments/fixtures-results',
  lacrosse_pll:'https://worldlacrosse.sport/events/',lacrosse_nll:'https://worldlacrosse.sport/events/',volleyball_w:'https://en.volleyballworld.com/global-schedule',volleyball_m:'https://en.volleyballworld.com/global-schedule'
};

const eventFnStart=source.indexOf('async function events(league){');
const providerFnStart=source.indexOf('\nasync function providerChannels',eventFnStart);
if(eventFnStart<0||providerFnStart<0)throw new Error('Unable to locate schedule loader in hotfix');
const scheduleCode=`const OFFICIAL_SCHEDULES=${JSON.stringify(officialSources)};
function flattenJsonLd(v,out=[]){if(Array.isArray(v)){for(const x of v)flattenJsonLd(x,out);return out;}if(!v||typeof v!=='object')return out;if(v['@graph'])flattenJsonLd(v['@graph'],out);if(v['@type'])out.push(v);return out;}
function parseOfficialJsonLd(html,league){const out=[];const re=/<script[^>]+type=[\\\"']application\\/ld\\+json[\\\"'][^>]*>([\\s\\S]*?)<\\/script>/gi;let m;while((m=re.exec(html))){try{const json=JSON.parse(m[1].replace(/<!--[\\s\\S]*?-->/g,'').trim());for(const x of flattenJsonLd(json)){const types=Array.isArray(x['@type'])?x['@type']:[x['@type']];if(!types.includes('Event')&&!types.includes('SportsEvent'))continue;const start=String(x.startDate||'').trim();if(!start)continue;const end=String(x.endDate||'').trim();const name=clean(x.name||x.headline||LEAGUES[league][0]);const loc=typeof x.location==='string'?x.location:clean(x.location?.name||x.location?.address?.addressLocality||'');const home=x.homeTeam?.name||x.competitor?.homeTeam?.name||'';const away=x.awayTeam?.name||x.competitor?.awayTeam?.name||'';const t=Date.parse(start),et=Date.parse(end);const state=Number.isFinite(t)&&t<=Date.now()&&(!Number.isFinite(et)||et>=Date.now())?'in':'pre';out.push({id:crypto.createHash('sha1').update(league+'|'+name+'|'+start).digest('hex').slice(0,16),league,leagueName:LEAGUES[league][0],start,state,home:{name:home||name,short:home||name,logo:x.homeTeam?.logo||''},away:{name:away||loc||LEAGUES[league][0],short:away||loc||LEAGUES[league][0],logo:x.awayTeam?.logo||''},detail:state==='in'?'LIVE':'Scheduled',broadcast:[],officialUrl:x.url||OFFICIAL_SCHEDULES[league]});}}catch(e){}}const now=Date.now(),cut=now+45*86400000;return out.filter(e=>{const t=Date.parse(e.start);return Number.isFinite(t)&&t>=now-2*86400000&&t<=cut;}).sort((a,b)=>Date.parse(a.start)-Date.parse(b.start)).slice(0,100);}
async function officialScheduleEvents(league){const url=OFFICIAL_SCHEDULES[league];if(!url)return[];return cached('official:'+league,60000,async()=>{try{const r=await axios.get(url,{timeout:9000,headers:{'User-Agent':'XSportsX/9.9 schedule-sync','Accept':'text/html,application/xhtml+xml'},maxContentLength:12000000});return parseOfficialJsonLd(String(r.data||''),league);}catch(err){console.error('[official-schedule:'+league+']',err.message);return[];}});}
async function events(league){const primary=await (async()=>{try{const d=await getJson(scoreboardUrl(league),5000);return(Array.isArray(d?.events)?d.events:[]).map(e=>normalizeEvent(league,e)).filter(e=>e.home.name!=='TBD'||e.away.name!=='TBD');}catch{return[];}})();return primary.length?primary:officialScheduleEvents(league);}
`;
source=source.slice(0,eventFnStart)+scheduleCode+source.slice(providerFnStart);

// Preserve venue, competition status and team records for the pre-source event details screen.
source=source.replace(
  "broadcast:(c?.broadcasts||[]).flatMap(x=>x.names||[])};",
  "broadcast:(c?.broadcasts||[]).flatMap(x=>x.names||[]),venue:c?.venue?.fullName||c?.venue?.address?.city||'',venueCity:c?.venue?.address?.city||'',venueState:c?.venue?.address?.state||'',homeRecord:cs.find(x=>x.homeAway==='home')?.records?.[0]?.summary||'',awayRecord:cs.find(x=>x.homeAway==='away')?.records?.[0]?.summary||'',notes:(c?.notes||[]).map(x=>x.headline||x.text).filter(Boolean),links:(e?.links||[]).map(x=>({href:x.href,text:x.text||x.shortText||''})).filter(x=>x.href)};"
);

// Keep UI aliases interchangeable with the server catalog ids.
const configFn='function config(req){return decrypt(tokenFrom(req));}';
if(source.includes(configFn)){
  source=source.replace(configFn,`const SPORT_ALIASES={volleyball_w:'ncaav',volleyball_m:'ncaav'};function config(req){const c=decrypt(tokenFrom(req));if(c&&Array.isArray(c.sports))c.sports=c.sports.map(x=>SPORT_ALIASES[x]||x);return c;}`);
}

// Return rich event details before the client asks for streams. This endpoint never touches provider playlists.
const streamMarker='const sm=p.match(/^\\/stream\\/tv\\/sport:([^:]+):([^/]+)\\.json$/);';
const metaRoute=`const md=p.match(/^\\/meta\\/tv\\/sport:([^:]+):([^/]+)\\.json$/);if(md&&c){const league=md[1],eventId=md[2];if(!(Array.isArray(c.sports)?c.sports:[]).includes(league))return json(res,200,{meta:null});const list=await events(league);const e=list.find(x=>x.id===eventId);if(!e)return json(res,200,{meta:null});return json(res,200,{meta:{id:\`sport:\${e.league}:\${e.id}\`,type:'tv',name:\`\${e.away.short||e.away.name} vs \${e.home.short||e.home.name}\`,league:e.leagueName,sport:e.league,start:e.start,state:e.state,detail:e.detail,home:e.home,away:e.away,venue:e.venue||'',venueCity:e.venueCity||'',venueState:e.venueState||'',records:{home:e.homeRecord||'',away:e.awayRecord||''},broadcasts:e.broadcast||[],notes:e.notes||[],officialUrl:e.officialUrl||'',links:e.links||[],sourceStatus:'ready-to-match'}});}if(!e){} `;
if(source.includes(streamMarker))source=source.replace(streamMarker,metaRoute+streamMarker);

const runner=new Function('require','process','__dirname','__filename','crypto',source);
runner(require,process,__dirname,target,require('crypto'));