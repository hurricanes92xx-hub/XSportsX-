const express = require('express');
const axios = require('axios');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const app = express();
app.disable('x-powered-by');
app.use((req,res,next)=>{res.setHeader('Access-Control-Allow-Origin','*');res.setHeader('Access-Control-Allow-Headers','*');next();});

const PORT=Number(process.env.PORT||10000);
const TIMEOUT=Number(process.env.REQUEST_TIMEOUT_MS||8000);
const SCHEDULE_TTL=Number(process.env.SCHEDULE_TTL_SECONDS||60)*1000;
const XTREAM_TTL=Number(process.env.XTREAM_TTL_SECONDS||300)*1000;
const FEED=path.join(__dirname,'data','schedule_feed.json');
const XTREAM_BASE=(process.env.XTREAM_BASE_URL||'').replace(/\/$/,'');
const XTREAM_USER=process.env.XTREAM_USERNAME||'';
const XTREAM_PASS=process.env.XTREAM_PASSWORD||'';
let scheduleCache={expires:0,events:[]};
let xtreamCache={expires:0,rows:[]};
const health=new Map();

function setHealth(key,ok,count,error=''){health.set(key,{ok,count,error,updatedAt:new Date().toISOString()});}
function clean(v){return String(v??'').replace(/\s+/g,' ').trim();}
const STOP=new Set(['the','and','at','vs','v','fc','cf','sc','club','team','live','tv','hd','fhd','uhd','4k','usa','us','network','sports','sport','channel','east','west','main','backup','feed','event','game']);
function norm(v){return clean(v).normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/&/g,' and ').replace(/[^a-z0-9]+/g,' ').split(/\s+/).filter(x=>x&&!STOP.has(x)).join(' ');}
function similarity(a,b){const aa=new Set(norm(a).split(' ').filter(Boolean)),bb=new Set(norm(b).split(' ').filter(Boolean));if(!aa.size||!bb.size)return 0;let hit=0;for(const x of aa)if(bb.has(x))hit++;return Math.round(hit/Math.min(aa.size,bb.size)*70+hit/new Set([...aa,...bb]).size*30);}
function stateFromTag(tag,start){const t=clean(tag).toUpperCase();if(t==='LIVE'||t==='IN_PROGRESS'||t==='IN')return'in';if(t==='FINAL'||t==='POST')return'post';const ms=Date.parse(start);return Number.isNaN(ms)?'pre':(ms<=Date.now()?'post':'pre');}
function feedEvent(e,index){const start=e.start||e.startUtc||'';const league=clean(e.league||'');const title=clean(e.title||league);const id=e.id||`feed:${crypto.createHash('sha1').update(`${league}|${title}|${start}`).digest('hex').slice(0,16)}`;const parts=title.split(/\s+@\s+|\s+vs\.?\s+/i);const away=clean(e.away||parts[0]||'');const home=clean(e.home||parts[1]||'');return{id,sport:clean(e.sport||league),league,title,startUtc:start,status:clean(e.status||e.tag||'Scheduled'),state:stateFromTag(e.tag,start),home,away,homeLogo:e.homeLogo||'',awayLogo:e.awayLogo||'',broadcast:clean(e.broadcast||''),artUrl:e.artUrl||'',sourceUrl:e.sourceUrl||'',source:e.source||'official',providerLeague:league,score:{home:e.homeScore??'',away:e.awayScore??''},_index:index};}
function loadFeed(){try{const raw=JSON.parse(fs.readFileSync(FEED,'utf8'));const rows=Array.isArray(raw.events)?raw.events.map(feedEvent).filter(e=>e.startUtc):[];setHealth('canonical-feed',rows.length>0,rows.length);return rows.sort((a,b)=>Date.parse(a.startUtc)-Date.parse(b.startUtc));}catch(e){setHealth('canonical-feed',false,0,e.message);return[];}}
function allEvents(){if(scheduleCache.expires>Date.now())return scheduleCache.events;const rows=loadFeed();scheduleCache={expires:Date.now()+SCHEDULE_TTL,events:rows};return rows;}
function eventsFor(league,days){const rows=allEvents();const now=Date.now(),end=now+Math.max(1,Math.min(7,Number(days)||3))*86400000;const key=norm(league);return rows.filter(e=>(!key||norm(e.league)===key)&&(()=>{const t=Date.parse(e.startUtc);return !Number.isNaN(t)&&t>=now-26*3600000&&t<=end;})());}
async function getXtream(){if(!XTREAM_BASE||!XTREAM_USER||!XTREAM_PASS){setHealth('xtream',false,0,'Xtream credentials not configured');return[];}if(xtreamCache.expires>Date.now())return xtreamCache.rows;try{const api=a=>{const u=new URL(`${XTREAM_BASE}/player_api.php`);u.searchParams.set('username',XTREAM_USER);u.searchParams.set('password',XTREAM_PASS);u.searchParams.set('action',a);return u.toString();};const[cats,streams]=await Promise.all([axios.get(api('get_live_categories'),{timeout:TIMEOUT}),axios.get(api('get_live_streams'),{timeout:TIMEOUT})]);const cm=new Map((Array.isArray(cats.data)?cats.data:[]).map(x=>[String(x.category_id),x.category_name||'Live TV']));xtreamCache.rows=(Array.isArray(streams.data)?streams.data:[]).map(s=>{const ext=String(s.container_extension||'ts').replace(/[^a-z0-9]/gi,'')||'ts';return{id:String(s.stream_id),name:s.name||`Channel ${s.stream_id}`,category:cm.get(String(s.category_id))||'Live TV',logo:s.stream_icon||'',url:`${XTREAM_BASE}/live/${encodeURIComponent(XTREAM_USER)}/${encodeURIComponent(XTREAM_PASS)}/${encodeURIComponent(s.stream_id)}.${ext}`};});xtreamCache.expires=Date.now()+XTREAM_TTL;setHealth('xtream',true,xtreamCache.rows.length);}catch(e){setHealth('xtream',false,xtreamCache.rows.length,e.message);}return xtreamCache.rows;}
const SPORT_CHANNEL_RE=/\b(espn|fox sports|fs1|fs2|tnt|tbs|trutv|nba|nfl|nhl|mlb|sec|acc|big ten|cbs sports|nbc sports|msg|bally|sports|fight|ufc|boxing|tennis|golf|racing|f1|nascar|soccer|football|basketball|hockey|baseball)\b/i;
function channelScore(s,e){const text=`${s.name} ${s.category}`;let score=similarity(text,`${e.away} ${e.home}`)*.78;for(const b of String(e.broadcast||'').split(',').map(clean).filter(Boolean))if(norm(text).includes(norm(b)))score=Math.max(score,94);if(SPORT_CHANNEL_RE.test(text))score+=8;if(/\b(4k|uhd)\b/i.test(text))score+=4;if(/\b(backup|alt|test)\b/i.test(text))score-=8;return Math.round(score);}
async function resolveStreams(event){if(!event)return[];const rows=(await getXtream()).filter(s=>SPORT_CHANNEL_RE.test(`${s.name} ${s.category}`));return rows.map(s=>({...s,score:channelScore(s,event)})).filter(s=>s.score>=35).sort((a,b)=>b.score-a.score).slice(0,12);}

const VERSION='3.0.0-canonical';
app.get('/',(req,res)=>res.json({name:'XSportsX Sports Source',version:VERSION,status:'ok',api:'/api/schedule?days=3',scheduleSource:'canonical-feed'}));
app.get('/health',(req,res)=>res.json({ok:true,source:'xsportsx-sports-source',version:VERSION,scheduleSource:'canonical-feed',providers:Object.fromEntries(health),cacheExpiresAt:scheduleCache.expires,xtreamConfigured:Boolean(XTREAM_BASE&&XTREAM_USER&&XTREAM_PASS),uptime:process.uptime()}));
app.get('/api/status',(req,res)=>res.json({ok:true,source:VERSION,scheduleSource:'canonical-feed',providers:Object.fromEntries(health)}));
app.get('/api/leagues',(req,res)=>{const names=[...new Set(allEvents().map(e=>e.league))].sort();res.json({source:VERSION,leagues:names.map((name,i)=>({id:`league-${i}`,name,sport:(allEvents().find(e=>e.league===name)||{}).sport||name,provider:'canonical'}))});});
app.get('/api/schedule',async(req,res)=>{try{const league=clean(req.query.league);const days=Math.max(1,Math.min(7,Number(req.query.days||3)));const events=eventsFor(league,days);res.set('Cache-Control','public, max-age=30, stale-while-revalidate=120');res.json({ok:true,source:VERSION,scheduleSource:'canonical-feed',updatedAt:new Date().toISOString(),days,league:league||'ALL',events});}catch(e){res.status(200).json({ok:false,source:VERSION,events:[],error:e.message});}});
app.get('/api/live',async(req,res)=>{const events=allEvents().filter(e=>e.state==='in');res.json({ok:true,source:VERSION,scheduleSource:'canonical-feed',updatedAt:new Date().toISOString(),events});});
app.get('/api/event/:id',async(req,res)=>{const id=decodeURIComponent(req.params.id);const e=allEvents().find(x=>x.id===id);res.json({ok:Boolean(e),event:e||null});});
app.get('/api/event/:id/streams',async(req,res)=>{try{const id=decodeURIComponent(req.params.id);const e=allEvents().find(x=>x.id===id);res.json({ok:Boolean(e),eventId:id,streams:await resolveStreams(e)});}catch(e){res.status(200).json({ok:false,streams:[],error:e.message});}});
app.get('/api/cache/refresh',async(req,res)=>{scheduleCache.expires=0;xtreamCache.expires=0;const events=allEvents();res.json({ok:true,events:events.length,cacheEntries:1});});

app.listen(PORT,'0.0.0.0',()=>console.log(`XSportsX canonical sports source listening on 0.0.0.0:${PORT}`));
