const fs=require('fs');
const path='hotfix-entry.js';
let s=fs.readFileSync(path,'utf8');
const marker='// XSPORTSX_PUBLIC_SOURCES_V2';
if(s.includes(marker)){console.log('XSportsX public sources already applied');process.exit(0);}
if(!s.includes("const {eventArtworkSvg}=require('./artwork');"))throw new Error('artwork import hook not found');
s=s.replace("const {eventArtworkSvg}=require('./artwork');","const {eventArtworkSvg}=require('./artwork');\nconst {publicChannels}=require('./public-sources');\n"+marker);
const old="const channels=await providerChannels(c);const ranked=channels.map(ch=>({...ch,score:score(e,ch)})).filter(x=>x.score>=20).sort((a,b)=>b.score-a.score).slice(0,8);";
const replacement="const channels=[...(await providerChannels(c)),...(await publicChannels())];const ranked=channels.map(ch=>({...ch,score:score(e,ch)})).filter(x=>x.score>=20).sort((a,b)=>b.score-a.score).slice(0,8);";
if(!s.includes(old))throw new Error('sports stream hook not found');
s=s.replace(old,replacement);
const oldUrl="function streamUrl(c,ch){if(c.source==='m3u')return ch.url;const x=c.xtream;return `${x.baseUrl.replace(/\\/$/,'')}/live/${encodeURIComponent(x.username)}/${encodeURIComponent(x.password)}/${encodeURIComponent(ch.streamId)}.ts`;}";
const newUrl="function streamUrl(c,ch){if(ch.public||c.source==='m3u')return ch.url;const x=c.xtream;return `${x.baseUrl.replace(/\\/$/,'')}/live/${encodeURIComponent(x.username)}/${encodeURIComponent(x.password)}/${encodeURIComponent(ch.streamId)}.ts`;}";
if(!s.includes(oldUrl))throw new Error('stream URL hook not found');
s=s.replace(oldUrl,newUrl);
fs.writeFileSync(path,s);
console.log('XSportsX public sources applied: backend only; UI untouched');
