import crypto from 'node:crypto';

const UA = process.env.REDDIT_USER_AGENT || 'XSportsX public-feed source monitor/1.4';
const MAX_FETCH_BYTES = 2 * 1024 * 1024;
const FETCH_TIMEOUT_MS = 8000;
const MAX_DEPTH = 4;
const MAX_FRONTIER = 75;
const seen = new Map();

function normalizeSubreddit(input){
  const s=String(input||'').trim();
  const m=s.match(/(?:reddit\.com|old\.reddit\.com|www\.reddit\.com)\/r\/([A-Za-z0-9_]+)|^r\/([A-Za-z0-9_]+)$|^([A-Za-z0-9_]+)$/i);
  return m?(m[1]||m[2]||m[3]):null;
}
function decodeEntities(s){return String(s||'').replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g,'$1').replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&#x27;/gi,"'");}
function stripTags(s){return decodeEntities(s).replace(/<br\s*\/?>(?=.)/gi,'\n').replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim();}
function tag(xml,name){const re=new RegExp(`<${name}(?:\\s[^>]*)?>([\\s\\S]*?)<\\/${name}>`,'i');const m=String(xml).match(re);return m?decodeEntities(m[1]):'';}
function decodeB64(value){
  const s=String(value||'').replace(/\s+/g,'');
  if(s.length<24||s.length%4===1||!/^[A-Za-z0-9+/=_-]+$/.test(s))return null;
  try{const out=Buffer.from(s.replace(/-/g,'+').replace(/_/g,'/'),'base64').toString('utf8');return out&&!/�/.test(out)?out:null;}catch{return null;}
}
function extractB64(text){
  const hits=[];
  for(const p of String(text||'').match(/[A-Za-z0-9+/_=-]{32,}/g)||[]){
    const d=decodeB64(p);
    if(d&&(d.includes('http://')||d.includes('https://')||d.includes('#EXTM3U')||d.includes('player_api.php')||d.includes('get.php')||d.toLowerCase().includes('stalker')))hits.push(d);
  }
  return [...new Set(hits)];
}
function urls(text){return [...new Set((String(text||'').match(/https?:\/\/[^\s"'<>]+/gi)||[]).map(x=>x.replace(/[\]\[),;]+$/g,'')))];}
function isIntermediate(url){
  try{const h=new URL(url).hostname.toLowerCase();return h==='reddit.com'||h.endsWith('.reddit.com')||h==='redd.it'||h.endsWith('.redd.it')||h==='paste.sh'||h.endsWith('.paste.sh');}catch{return true;}
}
function isCredentialedUrl(url){
  try{const u=new URL(url);return Boolean(u.username||u.password||u.searchParams.get('username')||u.searchParams.get('password')||u.searchParams.get('user')||u.searchParams.get('pass'));}catch{return true;}
}
function isPrivateHost(url){
  try{
    const h=new URL(url).hostname.toLowerCase();
    if(h==='localhost'||h.endsWith('.localhost')||h==='0.0.0.0'||h==='::1'||h.startsWith('127.')||h.startsWith('10.')||h.startsWith('192.168.'))return true;
    const m=h.match(/^172\.(\d+)\./);if(m&&Number(m[1])>=16&&Number(m[1])<=31)return true;
    return false;
  }catch{return true;}
}
function safeFetchTarget(url){
  try{const u=new URL(url);return ['http:','https:'].includes(u.protocol)&&!isPrivateHost(url)&&!isCredentialedUrl(url);}catch{return false;}
}
function parseIptvRecord(raw){
  const line=String(raw||'').trim();if(!line)return null;let u;try{u=new URL(line);}catch{return null;}
  if(!['http:','https:'].includes(u.protocol))return null;
  const query=new URLSearchParams(u.search),user=query.get('username')||query.get('user'),pass=query.get('password')||query.get('pass');
  const typeParam=(query.get('type')||'').toLowerCase(),path=u.pathname.toLowerCase(),text=line.toLowerCase();let type='direct';
  if(typeParam.includes('m3u')||path.includes('get.php')||text.includes('m3u_plus'))type='m3u';else if(path.includes('player_api.php')||text.includes('xtream'))type='xtream';else if(path.includes('portal.php')||text.includes('stalker'))type='stalker';else if(/\.(m3u8?|mpd)(?:$|\?)/i.test(path))type='m3u';
  if(!['m3u','xtream','stalker'].includes(type))return null;
  const base=new URL(u.origin+u.pathname);
  return{type,server:u.origin,endpoint:base.toString(),credentialPresent:Boolean(user||pass),credentialFields:[user?'username':null,pass?'password':null].filter(Boolean),rawUrl:line};
}
function maskCredentialUrl(url){
  try{const u=new URL(url);for(const k of ['username','password','user','pass'])if(u.searchParams.has(k))u.searchParams.set(k,'[hidden]');u.username='';u.password='';return u.toString();}catch{return'[hidden]';}
}
function inspectIptvText(text){
  const records=[];const counts={m3u:0,xtream:0,stalker:0};
  for(const line of String(text||'').split(/\r?\n/)){
    const record=parseIptvRecord(line);if(!record)continue;const key=`${record.type}|${record.server}|${record.endpoint}`;if(records.some(x=>x.key===key))continue;
    counts[record.type]++;records.push({key,type:record.type,server:record.server,endpoint:record.endpoint,credentialPresent:record.credentialPresent,credentialFields:record.credentialFields,displayUrl:maskCredentialUrl(record.rawUrl)});
  }
  return{records,counts,total:records.length};
}
function looksLikeSource(url,context=''){
  if(!url||isIntermediate(url))return false;const s=`${context}\n${url}`.toLowerCase();
  return/(?:#extm3u|#extinf|\.(?:m3u8?|mpd)(?:$|[?#])|\/portal\.php(?:$|[?#])|\bplaylist\b|\bstream\b|\blive\b|\biptv\b|\bxtream\b|(?:get|player_api)\.php\?)/i.test(s);
}
function itemsFromRss(xml){
  const items=[];const blocks=String(xml).match(/<entry\b[\s\S]*?<\/entry>/gi)||String(xml).match(/<item\b[\s\S]*?<\/item>/gi)||[];
  for(const block of blocks){
    const id=tag(block,'id')||tag(block,'guid')||tag(block,'link')||crypto.createHash('sha256').update(block).digest('hex').slice(0,24),title=stripTags(tag(block,'title')),summary=stripTags(tag(block,'content')||tag(block,'description')||tag(block,'summary'));
    const linkMatch=block.match(/<link[^>]+href=["']([^"']+)["'][^>]*>/i),link=linkMatch?decodeEntities(linkMatch[1]):stripTags(tag(block,'link')),published=tag(block,'published')||tag(block,'pubDate')||tag(block,'updated');
    items.push({id,title,text:`${title}\n${summary}\n${link}`,published,link});
  }return items;
}
async function fetchPublicText(url){
  if(!safeFetchTarget(url))return'';const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),FETCH_TIMEOUT_MS);
  try{const r=await fetch(url,{redirect:'follow',signal:controller.signal,headers:{'user-agent':UA,accept:'text/plain,text/html,application/json,application/vnd.apple.mpegurl,*/*'}});if(!r.ok)return'';const len=Number(r.headers.get('content-length')||0);if(len>MAX_FETCH_BYTES)return'';const buf=await r.arrayBuffer();if(buf.byteLength>MAX_FETCH_BYTES)return'';return Buffer.from(buf).toString('utf8');}catch{return'';}finally{clearTimeout(timer);}
}

// Reddit and paste URLs are intermediate documents: follow them, decode their contents,
// and only emit the actual IPTV endpoint discovered downstream.
async function expandDestination(startUrl,maxDepth=MAX_DEPTH){
  const found=new Map();let frontier=[startUrl];const visited=new Set();
  for(let depth=0;depth<maxDepth&&frontier.length;depth++){
    const next=[];
    for(const item of frontier){
      if(visited.has(item)||!safeFetchTarget(item))continue;visited.add(item);const text=await fetchPublicText(item);if(!text)continue;
      const inspected=inspectIptvText(text);
      for(const rec of inspected.records){const key=`${rec.type}|${rec.server}|${rec.endpoint}`;found.set(key,{url:rec.endpoint,type:rec.type,details:`IPTV ${rec.type.toUpperCase()} endpoint discovered${rec.credentialPresent?' • credential fields detected and hidden':''}`,server:rec.server,credentialPresent:rec.credentialPresent,credentialFields:rec.credentialFields,maskedExample:rec.displayUrl});}
      const decoded=extractB64(text),candidates=[...new Set([...urls(text),...decoded.flatMap(urls)])],context=`${text.slice(0,20000)}\n${decoded.join('\n')}`;
      for(const u of candidates){
        if(isIntermediate(u)){if(!visited.has(u)&&safeFetchTarget(u)&&depth+1<maxDepth)next.push(u);continue;}
        const rec=parseIptvRecord(u);
        if(rec){const key=`${rec.type}|${rec.server}|${rec.endpoint}`;found.set(key,{url:rec.endpoint,type:rec.type,details:`IPTV ${rec.type.toUpperCase()} endpoint discovered${rec.credentialPresent?' • credential fields detected and hidden':''}`,server:rec.server,credentialPresent:rec.credentialPresent,credentialFields:rec.credentialFields,maskedExample:maskCredentialUrl(rec.rawUrl)});continue;}
        if(looksLikeSource(u,context)&&!visited.has(u)&&safeFetchTarget(u)&&depth+1<maxDepth)next.push(u);
      }
    }
    frontier=[...new Set(next)].slice(0,MAX_FRONTIER);
  }return[...found.values()];
}
export async function scanSubreddit(input,{maxPosts=100}={}){
  const subreddit=normalizeSubreddit(input);if(!subreddit)throw new Error('Enter a valid subreddit URL such as https://www.reddit.com/r/example');
  const limit=Math.min(Math.max(Number(maxPosts)||100,1),100),endpoint=`https://www.reddit.com/r/${encodeURIComponent(subreddit)}/new/.rss?limit=${limit}`;
  const r=await fetch(endpoint,{headers:{'user-agent':UA,accept:'application/atom+xml, application/rss+xml, text/xml'}});if(!r.ok)throw new Error(`Reddit RSS returned HTTP ${r.status}`);
  const posts=itemsFromRss(await r.text()).slice(0,limit),discoveries=[],diagnostics={postsChecked:posts.length,base64Decoded:0,destinationsFetched:0,m3u:0,xtream:0,stalker:0,credentialedRecords:0};
  for(const p of posts){
    const decoded=extractB64(p.text);diagnostics.base64Decoded+=decoded.length;
    const destinations=[...new Set([...urls(p.text),...decoded.flatMap(urls)])].filter(u=>safeFetchTarget(u));
    for(const destination of destinations){diagnostics.destinationsFetched++;const expanded=await expandDestination(destination,MAX_DEPTH);
      for(const item of expanded){diagnostics[item.type]=(diagnostics[item.type]||0)+1;if(item.credentialPresent)diagnostics.credentialedRecords++;discoveries.push({id:crypto.createHash('sha256').update(`${p.id}|${item.type}|${item.server}|${item.url}`).digest('hex').slice(0,24),postId:p.id,title:p.title,subreddit,url:item.url,type:item.type,server:item.server,credentialPresent:item.credentialPresent,credentialFields:item.credentialFields,maskedExample:item.maskedExample,details:item.details,healthy:false,discoveredAt:p.published||new Date().toISOString(),postUrl:p.link});}
    }
  }
  return{subreddit,postsChecked:posts.length,diagnostics,discoveries:[...new Map(discoveries.map(x=>[`${x.type}|${x.server}|${x.url}`,x])).values()]};
}
export function startRedditMonitor({subreddit,onDiscover,intervalMs=15*60*1000}){
  const run=async()=>{try{const result=await scanSubreddit(subreddit);for(const item of result.discoveries){const key=`${subreddit}|${item.type}|${item.server}|${item.url}`;if(seen.has(key))continue;seen.set(key,Date.now());await onDiscover(item);}}catch(e){console.error('XSportsX Reddit RSS monitor:',e.message);}};
  run();return setInterval(run,Math.max(intervalMs,5*60*1000));
}
