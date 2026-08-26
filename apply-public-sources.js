const fs=require('fs');
const path='hotfix-entry.js';
let s=fs.readFileSync(path,'utf8');
function once(from,to,label){if(s.includes(to))return;if(!s.includes(from))throw new Error(`XSportsX source patch: missing ${label}`);s=s.replace(from,to);}

once("const {eventArtworkSvg}=require('./artwork');", "const {eventArtworkSvg}=require('./artwork');\nconst {publicChannels}=require('./public-sources');", 'public source import');

once("idPrefixes:['sport:','xtream:']", "idPrefixes:['sport:','xtream:','public:']", 'public id prefix');

once("{type:'tv',id:'starting-soon',name:'⚡ STARTING SOON',extra:[],showInHome:true},...sports.map", "{type:'tv',id:'starting-soon',name:'⚡ STARTING SOON',extra:[],showInHome:true},{type:'tv',id:'public-sports',name:'📡 PUBLIC SPORTS SOURCES',extra:[],showInHome:true},...sports.map", 'public catalog');

once("const cm=p.match(/^\\/catalog\\/tv\\/([^/]+)\\.json$/);if(cm&&c){const id=cm[1],allowed=new Set(Object.keys(LEAGUES));let ev=aggregateEvents(id,await allSportsEvents());", "const cm=p.match(/^\\/catalog\\/tv\\/([^/]+)\\.json$/);if(cm&&c){const id=cm[1];if(id==='public-sports'){const ch=await publicChannels();return json(res,200,{metas:ch.slice(0,250).map(x=>({id:`public:${x.streamId}`,type:'tv',name:x.name,poster:x.logo||`${base(req)}/artwork/other.svg`,background:x.logo||`${base(req)}/artwork/other.svg`,description:`${x.sourceName} • ${x.group||'Sports'}`,releaseInfo:new Date().toISOString(),genres:['Sports',x.sourceName],behaviorHints:{isPlayable:true}}))});}const allowed=new Set(Object.keys(LEAGUES));let ev=aggregateEvents(id,await allSportsEvents());", 'public catalog route');

once("const sm=p.match(/^\\/stream\\/tv\\/sport:([^:]+):([^/]+)\\.json$/);if(sm&&c){", "const pm=p.match(/^\\/stream\\/tv\\/public:([^/]+)\\.json$/);if(pm&&c){const channels=await publicChannels({health:true,healthLimit:24});const ch=channels.find(x=>x.streamId===pm[1]);return json(res,200,{streams:ch?[{title:`${ch.name} • ${ch.sourceName} • ${ch.health.score}% healthy`,url:ch.url,behaviorHints:{notWebReady:true}}]:[]});}const sm=p.match(/^\\/stream\\/tv\\/sport:([^:]+):([^/]+)\\.json$/);if(sm&&c){", 'public stream route');

once("const channels=await providerChannels(c);const ranked=channels.map(ch=>({...ch,score:score(e,ch)}))", "const channels=[...(await providerChannels(c)),...(await publicChannels({health:true,healthLimit:24}))];const ranked=channels.map(ch=>({...ch,score:score(e,ch)}))", 'event source merge');

once("function streamUrl(c,ch){if(c.source==='m3u')return ch.url;", "function streamUrl(c,ch){if(ch.public)return ch.url;if(c.source==='m3u')return ch.url;", 'public stream URL');

fs.writeFileSync(path,s);
console.log('XSportsX public source discovery + health checking applied');
