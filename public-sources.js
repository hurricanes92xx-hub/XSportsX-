const axios=require('axios');
const crypto=require('crypto');
const TTL=Number(process.env.PUBLIC_SOURCE_CACHE_TTL_SECONDS||900)*1000;
const MAX_BYTES=Number(process.env.PUBLIC_SOURCE_MAX_BYTES||30000000);
const cache=new Map();const inflight=new Map();
// Public playlists only. Authenticated/paid services remain user Xtream/M3U sources.
const SOURCES=[
 {id:'iptv-org-sports',name:'IPTV-org Sports',url:process.env.PUBLIC_IPTV_ORG_SPORTS_URL||'https://iptv-org.github.io/iptv/categories/sports.m3u'},
 {id:'free-tv',name:'Free-TV/IPTV',url:process.env.PUBLIC_FREE_TV_URL||'https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8'}
];
const clean=v=>String(v??'').replace(/\s+/g,' ').trim();
const sportRe=/\b(sport|sports|espn|espn\+|fox sports|fs1|fs2|tnt|tbs|nba|mlb|nhl|nfl|ncaaf|ncaab|wnba|sec network|sec|acc network|accnx|big ten|btn|bally|msg|regional sports|baseball|basketball|football|hockey|soccer|tennis|golf|cbs sports|nbc sports|bein|sky sport|f1|formula|racing|ufc|ufc fight pass|boxing|fight|paramount|tsn|sportsnet|peacock|fanduel|fifa\+|pbr|pll|overtime|nascar|pga|nhl network|mlb network|nba tv|nfl network|stadium|cbs|abc|nbc|fox|the cw)\b/i;
function parseM3U(text,source){const lines=String(text||'').split(/\r?\n/),out=[];for(let i=0;i<lines.length;i++){if(!/^#EXTINF/i.test(lines[i]))continue;const info=lines[i],url=lines[i+1]?.trim();if(!url||url.startsWith('#'))continue;const name=clean((info.match(/,(.*)$/)||[])[1]||'Channel'),logo=(info.match(/tvg-logo=["']([^"']*)/i)||[])[1]||'',group=(info.match(/group-title=["']([^"']*)/i)||[])[1]||'';if(!sportRe.test(`${name} ${group}`))continue;const streamId=crypto.createHash('sha1').update(`${source.id}|${url}`).digest('hex').slice(0,16);out.push({name,group,category:group,url,logo,sourceId:source.id,sourceName:source.name,streamId,public:true});}const seen=new Set();return out.filter(x=>{const k=`${x.name}|${x.url}`;if(seen.has(k))return false;seen.add(k);return true;});}
async function load(source){const key=source.id,hit=cache.get(key);if(hit&&hit.exp>Date.now())return hit.v;if(inflight.has(key))return inflight.get(key);const p=axios.get(source.url,{timeout:15000,responseType:'text',maxContentLength:MAX_BYTES,headers:{'User-Agent':'XSportsX-public-source/1.1','Accept':'application/vnd.apple.mpegurl,application/x-mpegURL,text/plain,*/*'}}).then(r=>parseM3U(r.data,source)).catch(e=>{console.warn(`[public-source:${source.id}] ${e.message}`);return[];}).then(v=>{cache.set(key,{v,exp:Date.now()+TTL});return v;}).finally(()=>inflight.delete(key));inflight.set(key,p);return p;}
async function publicChannels(){const lists=await Promise.all(SOURCES.map(load)),seen=new Set(),out=[];for(const list of lists)for(const ch of list){if(seen.has(ch.url))continue;seen.add(ch.url);out.push(ch);}return out;}
module.exports={publicChannels,SOURCES};
