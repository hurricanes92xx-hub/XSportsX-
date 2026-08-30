const express = require('express');
const axios = require('axios');

const app = express();
app.disable('x-powered-by');
app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', '*');
  next();
});

const PORT = Number(process.env.PORT || 10000);
const TIMEOUT = Number(process.env.REQUEST_TIMEOUT_MS || 8000);
const SCHEDULE_TTL = Number(process.env.SCHEDULE_TTL_SECONDS || 60) * 1000;
const NCAA_BASE = (process.env.NCAA_API_BASE_URL || 'https://ncaa-api.henrygd.me').replace(/\/$/, '');
const XTREAM_BASE_URL = (process.env.XTREAM_BASE_URL || '').replace(/\/$/, '');
const XTREAM_USERNAME = process.env.XTREAM_USERNAME || '';
const XTREAM_PASSWORD = process.env.XTREAM_PASSWORD || '';

const cache = new Map();
const inflight = new Map();
const providerHealth = new Map();
let xtreamCache = { expires: 0, rows: [] };

const LEAGUES = {
  nfl: { name:'NFL', sport:'football', league:'nfl', icon:'🏈', provider:'espn' },
  ncaaf: { name:'NCAA FB', sport:'football', league:'college-football', icon:'🏈', provider:'espn', params:{ groups:'80' } },
  ncaafcs: { name:'NCAA FCS', sport:'football', league:'college-football', icon:'🏈', provider:'espn', params:{ groups:'81' } },
  nba: { name:'NBA', sport:'basketball', league:'nba', icon:'🏀', provider:'espn' },
  wnba: { name:'WNBA', sport:'basketball', league:'wnba', icon:'🏀', provider:'espn' },
  ncaab: { name:'NCAA BB', sport:'basketball', league:'mens-college-basketball', icon:'🏀', provider:'espn' },
  ncaaw: { name:'NCAA WBB', sport:'basketball', league:'womens-college-basketball', icon:'🏀', provider:'espn' },
  mlb: { name:'MLB', sport:'baseball', league:'mlb', icon:'⚾', provider:'espn' },
  ncaabaseball: { name:'NCAA BASEBALL', sport:'baseball', league:'baseball', icon:'⚾', provider:'ncaa', ncaaSport:'baseball', division:'d1' },
  nhl: { name:'NHL', sport:'hockey', league:'nhl', icon:'🏒', provider:'espn' },
  ncaamhockey: { name:'NCAA MEN HOCKEY', sport:'hockey', league:'mens-college-hockey', icon:'🏒', provider:'ncaa', ncaaSport:'icehockey-men', division:'d1' },
  ncaawhockey: { name:'NCAA WOMEN HOCKEY', sport:'hockey', league:'womens-college-hockey', icon:'🏒', provider:'ncaa', ncaaSport:'icehockey-women', division:'d1' },
  ncaasoftball: { name:'NCAA SOFTBALL', sport:'softball', league:'softball', icon:'🥎', provider:'ncaa', ncaaSport:'softball', division:'d1' },
  ncaavb: { name:'NCAA VB', sport:'volleyball', league:'volleyball-women', icon:'🏐', provider:'ncaa', ncaaSport:'volleyball-women', division:'d1' },
  ncaamsoccer: { name:'NCAA MEN SOCCER', sport:'soccer', league:'soccer-men', icon:'⚽', provider:'ncaa', ncaaSport:'soccer-men', division:'d1' },
  ncaawsoccer: { name:'NCAA WOMEN SOCCER', sport:'soccer', league:'soccer-women', icon:'⚽', provider:'ncaa', ncaaSport:'soccer-women', division:'d1' },
  ncaamlax: { name:'NCAA MEN LAX', sport:'lacrosse', league:'mens-college-lacrosse', icon:'🥍', provider:'ncaa', ncaaSport:'lacrosse-men', division:'d1' },
  ncaawlax: { name:'NCAA WOMEN LAX', sport:'lacrosse', league:'womens-college-lacrosse', icon:'🥍', provider:'ncaa', ncaaSport:'lacrosse-women', division:'d1' },
  mls: { name:'MLS', sport:'soccer', league:'usa.1', icon:'⚽', provider:'espn' },
  epl: { name:'EPL', sport:'soccer', league:'eng.1', icon:'⚽', provider:'espn' },
  laliga: { name:'LaLiga', sport:'soccer', league:'esp.1', icon:'⚽', provider:'espn' },
  bundesliga: { name:'Bundesliga', sport:'soccer', league:'ger.1', icon:'⚽', provider:'espn' },
  seriea: { name:'Serie A', sport:'soccer', league:'ita.1', icon:'⚽', provider:'espn' },
  ligue1: { name:'Ligue 1', sport:'soccer', league:'fra.1', icon:'⚽', provider:'espn' },
  ucl: { name:'UCL', sport:'soccer', league:'uefa.champions', icon:'⚽', provider:'espn' },
  uel: { name:'UEL', sport:'soccer', league:'uefa.europa', icon:'⚽', provider:'espn' },
  nwsl: { name:'NWSL', sport:'soccer', league:'usa.nwsl', icon:'⚽', provider:'espn' },
  ufc: { name:'UFC', sport:'mma', league:'ufc', icon:'🥊', provider:'espn' },
  boxing: { name:'BOXING', sport:'boxing', league:'boxing', icon:'🥊', provider:'espn' }
};

const ALIASES = new Map([
  ['NFL','nfl'], ['NBA','nba'], ['WNBA','wnba'], ['NCAA FB','ncaaf'], ['NCAA FOOTBALL','ncaaf'], ['NCAAF','ncaaf'],
  ['NCAA FCS','ncaafcs'], ['NCAA BB','ncaab'], ['NCAA WBB','ncaaw'], ['MLB','mlb'], ['NCAA BASEBALL','ncaabaseball'],
  ['NHL','nhl'], ['NCAA MEN HOCKEY','ncaamhockey'], ['NCAA WOMEN HOCKEY','ncaawhockey'], ['NCAA SOFTBALL','ncaasoftball'],
  ['NCAA VB','ncaavb'], ['NCAA VOLLEYBALL','ncaavb'], ['NCAA MEN SOCCER','ncaamsoccer'], ["NCAA MEN'S SOCCER",'ncaamsoccer'],
  ['NCAA WOMEN SOCCER','ncaawsoccer'], ["NCAA WOMEN'S SOCCER",'ncaawsoccer'], ['NCAA MEN LAX','ncaamlax'], ['NCAA WOMEN LAX','ncaawlax'],
  ['MLS','mls'], ['EPL','epl'], ['LALIGA','laliga'], ['BUNDESLIGA','bundesliga'], ['SERIE A','seriea'], ['LIGUE 1','ligue1'],
  ['UCL','ucl'], ['UEL','uel'], ['NWSL','nwsl'], ['UFC','ufc'], ['BOXING','boxing']
]);

const STOP = new Set(['the','and','at','vs','v','fc','cf','sc','club','team','live','tv','hd','fhd','uhd','4k','usa','us','network','sports','sport','channel','east','west','main','backup','feed','event','game']);
const clean = v => String(v ?? '').replace(/\s+/g, ' ').trim();
const norm = v => clean(v).normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/&/g,' and ').replace(/[^a-z0-9]+/g,' ').split(/\s+/).filter(x => x && !STOP.has(x)).join(' ');
const toks = v => norm(v).split(' ').filter(Boolean);
function similarity(a,b){
  const aa = new Set(toks(a)); const bb = new Set(toks(b));
  if (!aa.size || !bb.size) return 0;
  let hit = 0; for (const x of aa) if (bb.has(x)) hit++;
  return Math.round((hit / Math.min(aa.size, bb.size) * 70) + (hit / new Set([...aa,...bb]).size * 30));
}
function sleep(ms){ return new Promise(r => setTimeout(r, ms)); }
function ymd(d){ return d.toISOString().slice(0,10).replace(/-/g,''); }
function cacheGet(key){ const x = cache.get(key); return x && x.expires > Date.now() ? x.value : null; }
function cached(key, loader, ttl=SCHEDULE_TTL){
  const hit = cacheGet(key); if (hit !== null) return Promise.resolve(hit);
  if (inflight.has(key)) return inflight.get(key);
  const p = Promise.resolve().then(loader).then(value => { cache.set(key,{value,expires:Date.now()+ttl}); return value; }).finally(() => inflight.delete(key));
  inflight.set(key,p); return p;
}
function setHealth(key, ok, count, error=''){ providerHealth.set(key,{ok,count,error,updatedAt:new Date().toISOString()}); }
function stateFrom(status, start){
  const state = String(status?.state || '').toLowerCase(); const name = String(status?.name || '').toLowerCase();
  if (state === 'in' || name.includes('in_progress') || name.includes('live')) return 'in';
  if (state === 'post' || name.includes('final') || name.includes('post')) return 'post';
  if (state === 'pre' || name.includes('scheduled') || name.includes('pre')) return 'pre';
  const t = Date.parse(start || ''); return t && t <= Date.now() ? 'post' : 'pre';
}

function espnEvent(key,e){
  const l = LEAGUES[key]; const c = e.competitions?.[0] || {}; const competitors = c.competitors || [];
  const home = competitors.find(x=>x.homeAway==='home') || competitors[0] || {}; const away = competitors.find(x=>x.homeAway==='away') || competitors[1] || {};
  const ht = home.team || {}; const at = away.team || {}; const start = e.date || c.date || ''; const status = c.status?.type || e.status?.type || {};
  if (!start && !ht.displayName && !at.displayName) return null;
  return {id:`sport:${key}:${e.id}`,sport:l.sport,league:l.name,title:(at.displayName&&ht.displayName)?`${at.displayName} vs ${ht.displayName}`:(e.name||`${l.name} event`),startUtc:start,status:status.shortDetail||status.detail||status.name||'Scheduled',state:stateFrom(status,start),home:ht.displayName||home.athlete?.displayName||'',away:at.displayName||away.athlete?.displayName||'',homeLogo:ht.logo||'',awayLogo:at.logo||'',broadcast:(c.broadcasts||[]).flatMap(x=>x.names||[]).join(', '),artUrl:ht.logo||at.logo||'',sourceUrl:`https://www.espn.com/${l.sport}/${l.league}`,source:'espn',providerLeague:key,score:{home:home.score??'',away:away.score??''}};
}

function ncaaEvent(key,g){
  const l = LEAGUES[key]; const x = g.game || g; const home = x.home || {}; const away = x.away || {};
  const hn = home.names?.full || home.names?.short || home.name || home.school || ''; const an = away.names?.full || away.names?.short || away.name || away.school || '';
  const parsedStart = x.startTimeEpoch ? new Date(Number(x.startTimeEpoch)*1000) : (x.startDate ? new Date(`${x.startDate} ${x.startTime||''}`) : null);
  const start = parsedStart && !Number.isNaN(parsedStart.getTime()) ? parsedStart.toISOString() : '';
  if (!hn || !an) return null;
  const gameState = String(x.gameState || '').toUpperCase(); const state = gameState==='I'?'in':gameState==='F'?'post':'pre';
  return {id:`sport:${key}:${x.gameID||x.gameId||x.contestId||`${ymd(parsedStart||new Date())}-${norm(an)}-${norm(hn)}`}`,sport:l.sport,league:l.name,title:`${an} vs ${hn}`,startUtc:start,status:gameState==='I'?'LIVE':gameState==='F'?(x.finalMessage||'FINAL'):'Scheduled',state,home:hn,away:an,homeLogo:'',awayLogo:'',broadcast:x.network||x.broadcasterName||'',artUrl:'',sourceUrl:x.url?`https://www.ncaa.com${x.url}`:'https://www.ncaa.com/',source:'ncaa',providerLeague:key,score:{home:home.score??'',away:away.score??''}};
}

async function fetchEspn(key){
  const l=LEAGUES[key]; const start=new Date(); start.setUTCDate(start.getUTCDate()-1); const end=new Date(); end.setUTCDate(end.getUTCDate()+3);
  const params=new URLSearchParams({dates:`${ymd(start)}-${ymd(end)}`,limit:'500',...(l.params||{})}); const url=`https://site.api.espn.com/apis/site/v2/sports/${l.sport}/${l.league}/scoreboard?${params}`;
  try{const r=await axios.get(url,{timeout:TIMEOUT});const events=(r.data?.events||[]).map(e=>espnEvent(key,e)).filter(Boolean);setHealth(`espn:${key}`,true,events.length);return events;}catch(e){setHealth(`espn:${key}`,false,0,e.message);return[];}
}
async function fetchNcaa(key){
  const l=LEAGUES[key]; const out=[]; const now=new Date();
  for(let i=-1;i<=3;i++){
    const d=new Date(now); d.setUTCDate(d.getUTCDate()+i); const url=`${NCAA_BASE}/scoreboard/${l.ncaaSport}/${l.division}/${ymd(d)}/all-conf`;
    try{const r=await axios.get(url,{timeout:TIMEOUT});const games=Array.isArray(r.data?.games)?r.data.games:[];out.push(...games.map(g=>ncaaEvent(key,g)).filter(Boolean));await sleep(220);}catch(e){providerHealth.set(`ncaa:${key}`,{ok:false,count:out.length,error:e.message,updatedAt:new Date().toISOString()});}
  }
  const unique=[...new Map(out.map(x=>[x.id,x])).values()]; setHealth(`ncaa:${key}`,unique.length>0,unique.length); return unique;
}
async function fetchLeague(key){ if(!LEAGUES[key]) return []; return cached(`league:${key}`,()=>LEAGUES[key].provider==='ncaa'?fetchNcaa(key):fetchEspn(key)); }
async function mapLimit(items,limit,fn){const out=[];let index=0;const worker=async()=>{while(true){const i=index++;if(i>=items.length)return;out[i]=await fn(items[i]);}};await Promise.all(Array.from({length:Math.min(limit,items.length)},worker));return out;}
async function allEvents(){return cached('all-events',async()=>{const parts=await mapLimit(Object.keys(LEAGUES),6,fetchLeague);return parts.flat().filter(e=>e&&e.startUtc).sort((a,b)=>Date.parse(a.startUtc)-Date.parse(b.startUtc));});}
async function schedule(league,days=3){const events=league?await fetchLeague(league):await allEvents();const now=Date.now(),end=now+Number(days)*86400000;return events.filter(e=>{const t=Date.parse(e.startUtc);return !Number.isNaN(t)&&t>=now-26*3600000&&t<=end;});}

const SPORT_CHANNEL_RE=/\b(espn|fox sports|fs1|fs2|tnt|tbs|trutv|nba|nfl|nhl|mlb|sec|acc|big ten|cbs sports|nbc sports|msg|bally|sports|fight|ufc|boxing|tennis|golf|racing|f1|nascar|soccer|football|basketball|hockey|baseball)\b/i;
async function getXtream(){
  if(!XTREAM_BASE_URL||!XTREAM_USERNAME||!XTREAM_PASSWORD)return[]; if(xtreamCache.expires>Date.now())return xtreamCache.rows;
  try{const api=action=>{const u=new URL(`${XTREAM_BASE_URL}/player_api.php`);u.searchParams.set('username',XTREAM_USERNAME);u.searchParams.set('password',XTREAM_PASSWORD);u.searchParams.set('action',action);return u.toString();};const[cats,streams]=await Promise.all([axios.get(api('get_live_categories'),{timeout:TIMEOUT}),axios.get(api('get_live_streams'),{timeout:TIMEOUT})]);const cm=new Map((Array.isArray(cats.data)?cats.data:[]).map(x=>[String(x.category_id),x.category_name||'Live TV']));xtreamCache.rows=(Array.isArray(streams.data)?streams.data:[]).map(s=>{const ext=String(s.container_extension||'ts').replace(/[^a-z0-9]/gi,'')||'ts';return{id:String(s.stream_id),name:s.name||`Channel ${s.stream_id}`,category:cm.get(String(s.category_id))||'Live TV',logo:s.stream_icon||'',url:`${XTREAM_BASE_URL}/live/${encodeURIComponent(XTREAM_USERNAME)}/${encodeURIComponent(XTREAM_PASSWORD)}/${encodeURIComponent(s.stream_id)}.${ext}`};});xtreamCache.expires=Date.now()+XTREAM_TTL;}catch(e){providerHealth.set('xtream',{ok:false,count:xtreamCache.rows.length,error:e.message,updatedAt:new Date().toISOString()});}return xtreamCache.rows;
}
function channelScore(s,e){const text=`${s.name} ${s.category}`;let score=similarity(text,`${e.away} ${e.home}`)*0.78;for(const b of String(e.broadcast||'').split(',').map(clean).filter(Boolean))if(norm(text).includes(norm(b)))score=Math.max(score,94);if(SPORT_CHANNEL_RE.test(text))score+=8;if(/\b(4k|uhd)\b/i.test(text))score+=4;if(/\b(backup|alt|test)\b/i.test(text))score-=8;return Math.round(score);}
async function resolveStreams(event){if(!event)return[];const rows=(await getXtream()).filter(s=>SPORT_CHANNEL_RE.test(`${s.name} ${s.category}`));return rows.map(s=>({...s,score:channelScore(s,event)})).filter(s=>s.score>=35).sort((a,b)=>b.score-a.score).slice(0,12);}

const SOURCE_VERSION='1.0.0';
app.get('/',(req,res)=>res.json({name:'XSportsX Sports Source',version:SOURCE_VERSION,status:'ok',api:'/api/schedule?days=3',health:'/health'}));
app.get('/health',(req,res)=>res.json({ok:true,source:'xsportsx-sports-source',version:SOURCE_VERSION,providers:Object.fromEntries(providerHealth),cacheEntries:cache.size,xtreamConfigured:Boolean(XTREAM_BASE_URL&&XTREAM_USERNAME&&XTREAM_PASSWORD),uptime:process.uptime()}));
app.get('/api/leagues',(req,res)=>res.json({source:SOURCE_VERSION,leagues:Object.entries(LEAGUES).map(([id,l])=>({id,name:l.name,sport:l.sport,provider:l.provider}))}));
app.get('/api/status',(req,res)=>res.json({ok:true,source:SOURCE_VERSION,providers:Object.fromEntries(providerHealth),cacheEntries:cache.size,xtreamConfigured:Boolean(XTREAM_BASE_URL&&XTREAM_USERNAME&&XTREAM_PASSWORD)}));
app.get('/api/schedule',async(req,res)=>{try{const raw=clean(req.query.league);const key=raw?(ALIASES.get(raw.toUpperCase())||raw.toLowerCase()):'';const days=Math.max(1,Math.min(7,Number(req.query.days||3)));const events=await schedule(key,days);res.set('Cache-Control','public, max-age=30, stale-while-revalidate=120');res.json({ok:true,source:SOURCE_VERSION,updatedAt:new Date().toISOString(),days,league:key||'ALL',events});}catch(e){res.status(200).json({ok:false,source:SOURCE_VERSION,events:[],error:e.message});}});
app.get('/api/live',async(req,res)=>{try{const events=await allEvents();res.json({ok:true,source:SOURCE_VERSION,updatedAt:new Date().toISOString(),events:events.filter(e=>e.state==='in')});}catch(e){res.status(200).json({ok:false,source:SOURCE_VERSION,events:[],error:e.message});}});
app.get('/api/event/:id',async(req,res)=>{try{const id=decodeURIComponent(req.params.id);const e=(await allEvents()).find(x=>x.id===id);res.json({ok:Boolean(e),event:e||null});}catch(e){res.status(200).json({ok:false,event:null,error:e.message});}});
app.get('/api/event/:id/streams',async(req,res)=>{try{const id=decodeURIComponent(req.params.id);const e=(await allEvents()).find(x=>x.id===id);res.json({ok:Boolean(e),eventId:id,streams:await resolveStreams(e)});}catch(e){res.status(200).json({ok:false,streams:[],error:e.message});}});
app.get('/api/cache/refresh',async(req,res)=>{cache.clear();inflight.clear();xtreamCache.expires=0;const events=await allEvents();res.json({ok:true,events:events.length,cacheEntries:cache.size});});

app.listen(PORT,'0.0.0.0',()=>console.log(`XSportsX Sports Source listening on 0.0.0.0:${PORT}`));
