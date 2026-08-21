const THEMES={
 nfl:['NFL','#e31837','FOOTBALL','LIVE GAMES'],ncaaf:['NCAA FOOTBALL','#39a7ff','COLLEGE FOOTBALL','LIVE GAMES'],nba:['NBA','#ff4b2f','BASKETBALL','LIVE GAMES'],wnba:['WNBA','#ff7a18','WOMEN’S BASKETBALL','LIVE GAMES'],ncaab:['NCAA BASKETBALL','#39a7ff','COLLEGE BASKETBALL','LIVE GAMES'],
 mlb:['MLB','#2aa7ff','BASEBALL','LIVE GAMES'],nhl:['NHL','#d8e1eb','ICE HOCKEY','LIVE GAMES'],mls:['MLS','#35e38a','SOCCER','LIVE GAMES'],epl:['PREMIER LEAGUE','#9b55ff','ENGLISH FOOTBALL','LIVE GAMES'],ucl:['CHAMPIONS LEAGUE','#35a7ff','EUROPEAN FOOTBALL','LIVE GAMES'],laliga:['LALIGA','#ff4b3d','SPANISH FOOTBALL','LIVE GAMES'],seriea:['SERIE A','#31a8ff','ITALIAN FOOTBALL','LIVE GAMES'],bundesliga:['BUNDESLIGA','#ff3045','GERMAN FOOTBALL','LIVE GAMES'],ligue1:['LIGUE 1','#baff00','FRENCH FOOTBALL','LIVE GAMES'],ufc:['UFC','#ff1738','COMBAT SPORTS','LIVE FIGHTS'],boxing:['BOXING','#ff1738','COMBAT SPORTS','LIVE FIGHTS'],other:['OTHER SPORTS','#ff9d1b','LIVE SPORTS','LIVE NOW']
};
const esc=v=>String(v??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const safeUrl=v=>String(v||'').replace(/&/g,'&amp;').replace(/"/g,'%22');
const truncate=(v,n=20)=>{const s=String(v||'');return s.length>n?`${s.slice(0,n-1)}…`:s};
function shellDefs(accent){return `<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#05070b"/><stop offset=".48" stop-color="#101722"/><stop offset="1" stop-color="#030408"/></linearGradient><linearGradient id="edge" x1="0" y1="0" x2="1" y2="1"><stop stop-color="${accent}" stop-opacity=".95"/><stop offset=".55" stop-color="#ffffff" stop-opacity=".2"/><stop offset="1" stop-color="${accent}" stop-opacity=".75"/></linearGradient><radialGradient id="orb"><stop stop-color="#182332"/><stop offset=".72" stop-color="#080c13"/><stop offset="1" stop-color="#03050a"/></radialGradient><filter id="shadow"><feDropShadow dx="0" dy="8" stdDeviation="10" flood-opacity=".65"/></filter></defs>`}
function brand(accent){return `<text x="42" y="43" fill="#fff" font-family="Arial,sans-serif" font-size="27" font-style="italic" font-weight="900" letter-spacing="2"><tspan fill="${accent}">X</tspan>SPORTS<tspan fill="${accent}">X</tspan></text><text x="44" y="66" fill="#8d98a7" font-family="Arial,sans-serif" font-size="8" font-weight="800" letter-spacing="3">LIVE SPORTS COMMAND CENTER</text>`}
function artworkSvg(id){const [name,accent,sub,status]=THEMES[id]||THEMES.other;const n=esc(name),s=esc(sub),st=esc(status);const fight=id==='ufc'||id==='boxing';return `<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 562">${shellDefs(accent)}<rect width="1000" height="562" rx="24" fill="url(#bg)"/><rect x="4" y="4" width="992" height="554" rx="22" fill="none" stroke="url(#edge)" stroke-width="4"/><path d="M-30 562L300 0h250L180 562Z" fill="${accent}" opacity=".09"/><path d="M650 0L1000 380V562H830L540 0Z" fill="${accent}" opacity=".07"/><path d="M0 438H1000" stroke="#fff" stroke-width="2" opacity=".06"/>${brand(accent)}<g opacity=".18" stroke="${accent}" fill="none" stroke-width="4">${fight?'<path d="M690 145l85 35 30 80-65 75-95-45 20-100z"/><path d="M820 300l70-45 65 70-60 95-80-40z"/>':'<circle cx="810" cy="280" r="150"/><path d="M660 280h300M810 130v300M700 170l220 220M920 170L700 390"/>'}</g><text x="58" y="350" fill="#fff" font-family="Arial,sans-serif" font-size="65" font-style="italic" font-weight="900">${n}</text><text x="62" y="389" fill="${accent}" font-family="Arial,sans-serif" font-size="14" font-weight="900" letter-spacing="4">${s}</text><rect x="62" y="414" width="280" height="4" rx="2" fill="${accent}"/><text x="62" y="455" fill="#f5f7fa" font-family="Arial,sans-serif" font-size="14" font-weight="900" letter-spacing="4">${st}</text><text x="950" y="525" text-anchor="end" fill="#fff" opacity=".25" font-family="Arial,sans-serif" font-size="10" font-weight="800" letter-spacing="3">XSX / ${esc(id.toUpperCase())}</text></svg>`}
function eventArtworkSvg(league,away,home,state='pre',start='',awayLogo='',homeLogo='',awayShort='',homeShort=''){
 const [lname,accent]=THEMES[league]||THEMES.other;
 const a=truncate(away||'AWAY',22),h=truncate(home||'HOME',22);
 const as=truncate(awayShort||a,7),hs=truncate(homeShort||h,7);
 const live=state==='in',post=state==='post';
 const when=live?'LIVE NOW':post?'FINAL':start?new Date(start).toLocaleString('en-US',{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}):'UPCOMING';
 const logo=(data,x)=>data?`<image href="${safeUrl(data)}" x="${x-67}" y="151" width="134" height="134" preserveAspectRatio="xMidYMid meet"/>`:'';
 const team=(x,name,short,data)=>`<g filter="url(#shadow)"><circle cx="${x}" cy="235" r="82" fill="url(#orb)" stroke="${accent}" stroke-opacity=".75" stroke-width="3"/><circle cx="${x}" cy="235" r="72" fill="none" stroke="#fff" stroke-opacity=".06" stroke-width="2"/>${logo(data,x)}${!data?`<text x="${x}" y="248" text-anchor="middle" fill="#fff" font-family="Arial,sans-serif" font-size="32" font-weight="900">${esc(short)}</text>`:''}</g><text x="${x}" y="348" text-anchor="middle" fill="#fff" font-family="Arial,sans-serif" font-size="23" font-weight="900">${esc(name)}</text>`;
 return `<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 562" width="1000" height="562">
 ${shellDefs(accent)}
 <rect width="1000" height="562" rx="24" fill="url(#bg)"/>
 <rect x="4" y="4" width="992" height="554" rx="22" fill="none" stroke="url(#edge)" stroke-width="4"/>
 <path d="M0 562L275 0h240L195 562Z" fill="${accent}" opacity=".11"/><path d="M735 0L1000 335V562H830L555 0Z" fill="${accent}" opacity=".07"/>
 <path d="M0 118H1000M0 420H1000" stroke="#fff" stroke-width="2" opacity=".06"/>
 ${brand(accent)}
 <rect x="389" y="34" width="222" height="30" rx="15" fill="${accent}" opacity=".14" stroke="${accent}" stroke-width="1"/>
 <text x="500" y="54" text-anchor="middle" fill="${accent}" font-family="Arial,sans-serif" font-size="11" font-weight="900" letter-spacing="3">${esc(lname)} • ${esc(when)}</text>
 ${team(250,a,as,awayLogo)}
 ${team(750,h,hs,homeLogo)}
 <circle cx="500" cy="235" r="48" fill="#05070b" stroke="${accent}" stroke-width="3"/><circle cx="500" cy="235" r="38" fill="none" stroke="#fff" stroke-opacity=".08"/>
 <text x="500" y="243" text-anchor="middle" fill="#fff" font-family="Arial,sans-serif" font-size="21" font-style="italic" font-weight="900" letter-spacing="2">VS</text>
 <path d="M65 397H935" stroke="#fff" stroke-width="1" opacity=".08"/>
 <rect x="365" y="407" width="270" height="34" rx="17" fill="${live?'#d7193f':post?'#7b8490':accent}" opacity=".16" stroke="${live?'#d7193f':post?'#7b8490':accent}" stroke-width="1"/>
 <circle cx="393" cy="424" r="5" fill="${live?'#ff294f':post?'#aab2bd':accent}"/>
 <text x="500" y="429" text-anchor="middle" fill="#f7f9fb" font-family="Arial,sans-serif" font-size="12" font-weight="900" letter-spacing="2">${live?'LIVE • STREAMS AVAILABLE':post?'FINAL • WATCH AVAILABLE':'STREAM OPTIONS AVAILABLE'}</text>
 <text x="500" y="477" text-anchor="middle" fill="#fff" opacity=".36" font-family="Arial,sans-serif" font-size="10" font-weight="800" letter-spacing="4">GAME CENTER • XSPORTSX</text>
 <text x="950" y="525" text-anchor="end" fill="#fff" opacity=".22" font-family="Arial,sans-serif" font-size="9" font-weight="800" letter-spacing="3">${esc(league.toUpperCase())}</text>
 </svg>`;
}
module.exports={THEMES,artworkSvg,eventArtworkSvg};
