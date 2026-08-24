const fs = require('fs');
const path = require('path');
const http = require('http');

// Render terminates TLS at its proxy. Keep absolute addon URLs HTTPS.
const originalCreateServer = http.createServer;
http.createServer = function wrappedCreateServer(handler) {
  return originalCreateServer.call(http, (req, res) => {
    if (req.url && req.url.startsWith('/')) {
      const host = req.headers.host || 'localhost';
      req.url = `https://${host}${req.url}`;
    }
    return handler(req, res);
  });
};

const appPath = path.join(__dirname, 'app96.js');
let source = fs.readFileSync(appPath, 'utf8');

// Preserve the health/artwork routing fix.
const bad = "return json(res,200,{ok:true,version:VERSION})}if(req.method==='GET'&&u.pathname==='/artwork.svg')";
const good = "return json(res,200,{ok:true,version:VERSION});if(req.method==='GET'&&u.pathname==='/artwork.svg')";
if (source.includes(bad)) source = source.replace(bad, good);

// Always expose the complete XSportsX sports catalog set. The previous
// configuration stored only selected sports in the encrypted token, which
// caused Nuvio to receive only a subset of catalogs after reinstall.
const decryptFix = "function decrypt(t){try{const[a,b,c]=String(t||'').split('.');if(!a||!b||!c)return null;const d=crypto.createDecipheriv('aes-256-gcm',KEY,Buffer.from(a,'base64url'));d.setAuthTag(Buffer.from(b,'base64url'));const v=JSON.parse(Buffer.concat([d.update(Buffer.from(c,'base64url')),d.final()]).toString());if(v&&Array.isArray(v.sports)&&typeof LEAGUES!=='undefined')v.sports=LEAGUES.map(x=>x[0]);return v}catch{return null}}function normalizeXtream";
source = source.replace(/function decrypt\(t\)\{[\s\S]*?\}(?=function normalizeXtream)/, decryptFix);

// The previous meta handler left the literal `event:` prefix in the lookup
// key, so clicking a catalog item produced "Failed to load". Use the exact
// event token after removing the prefix and support both old and new IDs.
const oldEventMeta = "function eventMeta(id,e,base){const l=LEAGUE(id);return{id:`sports:${id}:event:${encodeURIComponent(e.sourceId||eventKey(e))}`,type:'tv',name:`${e.away} vs ${e.home}`,poster:`${base}/artwork.svg`,posterShape:'landscape',releaseInfo:new Date(e.start).toISOString().slice(0,10),description:`${e.status==='live'?'LIVE • ':''}${new Date(e.start).toLocaleString()} • ${l[1]} • ${[...(e.broadcasts||[])].slice(0,4).join(', ')}`,genres:[l[1]]}}";
const newEventMeta = "function eventMeta(id,e,base){const l=LEAGUE(id),key=Buffer.from(String(e.sourceId||eventKey(e))).toString('base64url');return{id:`sports:${id}:event:${key}`,type:'tv',name:`${e.away} vs ${e.home}`,poster:`${base}/artwork.svg`,posterShape:'landscape',releaseInfo:new Date(e.start).toISOString().slice(0,10),description:`${e.status==='live'?'LIVE • ':''}${new Date(e.start).toLocaleString()} • ${l[1]} • ${[...(e.broadcasts||[])].slice(0,6).join(', ')}`,genres:[l[1]]}}";
if (source.includes(oldEventMeta)) source = source.replace(oldEventMeta, newEventMeta);

// Replace UFC parsing with a safer official-event parser.
const oldUfc = source.match(/async function ufcOfficial\(\)\{[\s\S]*?\}\s*async function ncaaOfficial/);
const newUfc = `async function ufcOfficial(){try{const html=await fetchText('https://www.ufc.com/events');const text=html.replace(/<script[\\s\\S]*?<\\/script>/gi,' ').replace(/<style[\\s\\S]*?<\\/style>/gi,' ').replace(/<[^>]+>/g,' ').replace(/&nbsp;/gi,' ').replace(/&amp;/gi,'&').replace(/\\s+/g,' ');const out=[];const re=/([A-Z][A-Za-z.'-]+(?:\\s+[A-Z][A-Za-z.'-]+){0,3}\\s+vs\\s+[A-Z][A-Za-z.'-]+(?:\\s+[A-Z][A-Za-z.'-]+){0,3})\\s+(?:Sat|Sun|Fri|Thu|Wed|Tue|Mon),\\s*([A-Z][a-z]{2})\\s+(\\d{1,2})\\s*\\/\\s*(\\d{1,2}:\\d{2}\\s*[AP]M)\\s*\\/\\s*Main Card/gi;let m;const months={Jan:0,Feb:1,Mar:2,Apr:3,May:4,Jun:5,Jul:6,Aug:7,Sep:8,Oct:9,Nov:10,Dec:11};const now=new Date();const year=now.getFullYear();while((m=re.exec(text))){const title=m[1].trim();if(/\\bTBD\\b/i.test(title))continue;const parts=title.split(/\\s+vs\\s+/i);if(parts.length!==2)continue;const month=months[m[2]];if(month===undefined)continue;const hm=m[4].match(/(\\d{1,2}):(\\d{2})\\s*([AP]M)/i);if(!hm)continue;let h=Number(hm[1])%12;if(hm[3].toUpperCase()==='PM')h+=12;const utcOffset=(month>=2&&month<=10)?4:5;const start=new Date(Date.UTC(year,month,Number(m[3]),h,Number(hm[2]))+utcOffset*60*60*1000);if(start.getTime()<Date.now()-4*60*60*1000||start.getTime()>Date.now()+30*24*60*60*1000)continue;out.push({league:'ufc',source:'UFC.com',sourceId:'ufc-'+start.getTime()+'-'+norm(title),away:parts[0].trim(),home:parts[1].trim(),start:start.toISOString(),status:'scheduled',broadcasts:['Paramount+']});}return out}catch{return[]}} async function ncaaOfficial`;
if (oldUfc) source = source.replace(oldUfc[0], newUfc);

// Prevent generic ESPN placeholders from entering any catalog.
const oldEspn = "function espnNormalize(id,e){const c=e.competitions?.[0],teams=c?.competitors||[];const away=teams.find(x=>x.homeAway==='away'),home=teams.find(x=>x.homeAway==='home');const status=c?.status?.type;return{league:id,source:'ESPN',sourceId:String(e.id),away:away?.team?.displayName||teams[0]?.team?.displayName||'Away',home:home?.team?.displayName||teams[1]?.team?.displayName||'Home',awayShort:away?.team?.abbreviation,homeShort:home?.team?.abbreviation,start:e.date,status:status?.completed?'final':/postponed/i.test(status?.name||'')?'postponed':status?.state==='in'?'live':'scheduled',broadcasts:(c?.broadcasts||[]).flatMap(x=>[x.names,x.market,x.type?.shortName,x.type?.longName]).flat().filter(Boolean)}}";
const newEspn = "function espnNormalize(id,e){const c=e.competitions?.[0],teams=c?.competitors||[];const away=teams.find(x=>x.homeAway==='away'),home=teams.find(x=>x.homeAway==='home');const awayName=away?.team?.displayName||teams[0]?.team?.displayName;const homeName=home?.team?.displayName||teams[1]?.team?.displayName;if(!awayName||!homeName||/^away$/i.test(awayName)||/^home$/i.test(homeName)||/^tbd$/i.test(awayName)||/^tbd$/i.test(homeName))return null;const status=c?.status?.type;return{league:id,source:'ESPN',sourceId:String(e.id),away:awayName,home:homeName,awayShort:away?.team?.abbreviation,homeShort:home?.team?.abbreviation,start:e.date,status:status?.completed?'final':/postponed/i.test(status?.name||'')?'postponed':status?.state==='in'?'live':'scheduled',broadcasts:(c?.broadcasts||[]).flatMap(x=>[x.names,x.market,x.type?.shortName,x.type?.longName]).flat().filter(Boolean)}}";
if (source.includes(oldEspn)) source = source.replace(oldEspn, newEspn);
source = source.replace("all.push(...await espn(id));const v=cacheSet(k,mergeEvents(all),20000);", "all.push(...(await espn(id)).filter(Boolean));const v=cacheSet(k,mergeEvents(all),20000);");

// Robustly resolve both new base64url IDs and old IDs.
const oldMetaHandler = "if(parts[1]==='meta'&&parts[2]==='tv'&&parts[3]){const rid=parts[3].replace(/\\.json$/,'');const id=rid.split(':')[1]||c.sports[0];const ev=await schedules(id);const e=ev.find(x=>String(x.sourceId)===decodeURIComponent(rid.split(':').slice(2).join(':')));return json(res,200,{meta:e?eventMeta(id,e,u.origin):null})}";
const newMetaHandler = "if(parts[1]==='meta'&&parts[2]==='tv'&&parts[3]){const rid=parts[3].replace(/\\.json$/,'');const bits=rid.split(':');const id=bits[1]||c.sports[0];if(!VALID.has(id))return json(res,200,{meta:null});let raw=bits.slice(2).join(':').replace(/^event:/,'');try{raw=Buffer.from(raw,'base64url').toString('utf8')}catch{}const ev=await schedules(id);const e=ev.find(x=>String(x.sourceId)===decodeURIComponent(raw)||eventKey(x)===decodeURIComponent(raw));return json(res,200,{meta:e?eventMeta(id,e,u.origin):null})}";
if (source.includes(oldMetaHandler)) source = source.replace(oldMetaHandler, newMetaHandler);

const oldStreamHandler = "if(parts[1]==='stream'&&parts[2]==='tv'&&parts[3]){const rid=parts[3].replace(/\\.json$/,'');const bits=rid.split(':');const id=bits[1];if(!VALID.has(id))return json(res,200,{streams:[]});const raw=bits.slice(2).join(':').replace(/^event:/,'');return json(res,200,{streams:await streamsForEvent(c,id,raw,u.origin)})}";
const newStreamHandler = "if(parts[1]==='stream'&&parts[2]==='tv'&&parts[3]){const rid=parts[3].replace(/\\.json$/,'');const bits=rid.split(':');const id=bits[1];if(!VALID.has(id))return json(res,200,{streams:[]});let raw=bits.slice(2).join(':').replace(/^event:/,'');try{raw=Buffer.from(raw,'base64url').toString('utf8')}catch{}return json(res,200,{streams:await streamsForEvent(c,id,raw,u.origin)})}";
if (source.includes(oldStreamHandler)) source = source.replace(oldStreamHandler, newStreamHandler);

const oldStreamsForEvent = "let decoded=decodeURIComponent(rawId);let e=ev.find(x=>String(x.sourceId)===decoded);if(!e){const n=decoded.split(':');const guess=norm(n.slice(-1)[0]);e=ev.find(x=>norm(`${x.away} ${x.home}`)===guess)}if(!e)return[];";
const newStreamsForEvent = "let decoded=decodeURIComponent(rawId);let e=ev.find(x=>String(x.sourceId)===decoded||eventKey(x)===decoded);if(!e){const n=decoded.split(':');const guess=norm(n.slice(-1)[0]);e=ev.find(x=>norm(`${x.away} ${x.home}`)===guess)}if(!e)return[];";
if (source.includes(oldStreamsForEvent)) source = source.replace(oldStreamsForEvent, newStreamsForEvent);

fs.writeFileSync(appPath, source);
require(appPath);
