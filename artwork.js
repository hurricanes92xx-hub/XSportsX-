const THEMES={
 nfl:['NFL','#e31837','FOOTBALL','LIVE GAMES'],ncaaf:['NCAA FOOTBALL','#39a7ff','COLLEGE FOOTBALL','LIVE GAMES'],nba:['NBA','#ff4b2f','BASKETBALL','LIVE GAMES'],wnba:['WNBA','#ff7a18','WOMEN’S BASKETBALL','LIVE GAMES'],ncaab:['NCAA BASKETBALL','#39a7ff','COLLEGE BASKETBALL','LIVE GAMES'],
 mlb:['MLB','#2aa7ff','BASEBALL','LIVE GAMES'],nhl:['NHL','#d8e1eb','ICE HOCKEY','LIVE GAMES'],mls:['MLS','#35e38a','SOCCER','LIVE GAMES'],epl:['PREMIER LEAGUE','#9b55ff','ENGLISH FOOTBALL','LIVE GAMES'],ucl:['CHAMPIONS LEAGUE','#35a7ff','EUROPEAN FOOTBALL','LIVE GAMES'],laliga:['LALIGA','#ff4b3d','SPANISH FOOTBALL','LIVE GAMES'],seriea:['SERIE A','#31a8ff','ITALIAN FOOTBALL','LIVE GAMES'],bundesliga:['BUNDESLIGA','#ff3045','GERMAN FOOTBALL','LIVE GAMES'],ligue1:['LIGUE 1','#baff00','FRENCH FOOTBALL','LIVE GAMES'],ufc:['UFC','#ff1738','COMBAT SPORTS','LIVE FIGHTS'],boxing:['BOXING','#ff1738','COMBAT SPORTS','LIVE FIGHTS'],other:['OTHER SPORTS','#ff9d1b','LIVE SPORTS','LIVE NOW']
};
const esc=v=>String(v??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const safeUrl=v=>String(v||'').replace(/&/g,'&amp;').replace(/"/g,'%22');
function shellDefs(accent){return `<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#020305"/><stop offset=".48" stop-color="#0b111a"/><stop offset="1" stop-color="#020204"/></linearGradient><linearGradient id="beam" x1="0" y1="0" x2="1" y2="1"><stop stop-color="${accent}" stop-opacity=".8"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient></defs>`}
function brand(accent){return `<text x="44" y="45" fill="#fff" font-family="Arial,sans-serif" font-size="28" font-style="italic" font-weight="900" letter-spacing="2"><tspan fill="${accent}">X</tspan>SPORTS<tspan fill="${accent}">X</tspan></text><text x="46" y="71" fill="#9da8b5" font-family="Arial,sans-serif" font-size="9" font-weight="800" letter-spacing="3">LIVE SPORTS COMMAND CENTER</text>`}
function artworkSvg(id){const [name,accent,sub,status]=THEMES[id]||THEMES.other;const n=esc(name),s=esc(sub),st=esc(status);const fight=id==='ufc'||id==='boxing';return `<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 562">${shellDefs(accent)}<rect width="1000" height="562" fill="url(#bg)"/><path d="M-40 560L350 0h210L170 562Z" fill="${accent}" opacity=".10"/><path d="M540 0L920 562" stroke="${accent}" stroke-width="130" opacity=".08"/><path d="M620 0L1000 410" stroke="#fff" stroke-width="2" opacity=".14"/><path d="M0 475L285 80" stroke="${accent}" stroke-width="3" opacity=".7"/><path d="M650 65h285M650 72h185" stroke="${accent}" stroke-width="3" opacity=".8"/><g opacity=".2" stroke="${accent}" fill="none" stroke-width="4">${fight?'<path d="M650 150l80 35 35 85-65 60-85-40 20-100z"/><path d="M790 310l90-45 55 75-65 90-85-45z"/>':'<circle cx="790" cy="285" r="155"/><path d="M635 285h310M790 130v310M680 175l220 220M900 175L680 395"/>'}</g>${brand(accent)}<text x="58" y="360" fill="#fff" font-family="Arial,sans-serif" font-size="67" font-style="italic" font-weight="900" letter-spacing="-1">${n}</text><text x="62" y="398" fill="${accent}" font-family="Arial,sans-serif" font-size="14" font-weight="900" letter-spacing="4">${s}</text><rect x="62" y="423" width="300" height="4" fill="url(#beam)"/><text x="62" y="463" fill="#f5f7fa" font-family="Arial,sans-serif" font-size="15" font-weight="900" letter-spacing="4">${st}</text><text x="950" y="525" text-anchor="end" fill="#fff" opacity=".3" font-family="Arial,sans-serif" font-size="10" font-weight="800" letter-spacing="3">XSX / ${esc(id.toUpperCase())}</text></svg>`}
function eventArtworkSvg(league,away,home,state='pre',start='',awayLogo='',homeLogo=''){
 const [lname,accent]=THEMES[league]||THEMES.other;
 const a=esc(away||'AWAY'),h=esc(home||'HOME');
 const when=state==='in'?'LIVE NOW':start?new Date(start).toLocaleString('en-US',{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}):'UPCOMING';
 const live=state==='in';
 const logo=(data,x)=>data?`<image href="${safeUrl(data)}" x="${x-68}" y="194" width="136" height="136" preserveAspectRatio="xMidYMid meet"/>`:'';
 const team=(x,name,data)=>`<rect x="${x-92}" y="160" width="184" height="190" rx="28" fill="#070b11" stroke="${accent}" stroke-width="3"/><circle cx="${x}" cy="228" r="70" fill="#0b1018" stroke="#ffffff" stroke-opacity=".14" stroke-width="2"/>${logo(data,x)}<text x="${x}" y="375" text-anchor="middle" fill="#fff" font-family="Arial,sans-serif" font-size="25" font-weight="900">${esc(name)}</text>`;
 return `<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 562" width="1000" height="562">
 ${shellDefs(accent)}
 <rect width="1000" height="562" fill="url(#bg)"/>
 <path d="M0 562L285 0h250L210 562Z" fill="${accent}" opacity=".13"/>
 <path d="M720 0L1000 340V562H815L540 0Z" fill="${accent}" opacity=".08"/>
 <path d="M0 126H1000M0 438H1000" stroke="#fff" stroke-width="2" opacity=".08"/>
 <path d="M0 562L260 90M740 0L1000 470" stroke="${accent}" stroke-width="4" opacity=".6"/>
 ${brand(accent)}
 <text x="500" y="105" text-anchor="middle" fill="${accent}" font-family="Arial,sans-serif" font-size="13" font-weight="900" letter-spacing="4">${esc(lname)} • ${esc(when)}</text>
 ${team(250,a,awayLogo)}
 ${team(750,h,homeLogo)}
 <circle cx="500" cy="228" r="52" fill="#05070b" stroke="${accent}" stroke-width="3"/>
 <text x="500" y="237" text-anchor="middle" fill="#fff" font-family="Arial,sans-serif" font-size="23" font-style="italic" font-weight="900" letter-spacing="2">VS</text>
 <rect x="365" y="407" width="270" height="4" rx="2" fill="${accent}"/>
 <text x="500" y="446" text-anchor="middle" fill="#f4f6f8" font-family="Arial,sans-serif" font-size="13" font-weight="900" letter-spacing="3">${live?'● LIVE STREAMS AVAILABLE':'STREAM OPTIONS AVAILABLE'}</text>
 <text x="500" y="484" text-anchor="middle" fill="#fff" opacity=".4" font-family="Arial,sans-serif" font-size="10" font-weight="800" letter-spacing="4">XSX • GAME CENTER • XSPORTSX</text>
 <text x="950" y="525" text-anchor="end" fill="#fff" opacity=".22" font-family="Arial,sans-serif" font-size="10" font-weight="800" letter-spacing="3">${esc(league.toUpperCase())}</text>
 </svg>`;
}
module.exports={THEMES,artworkSvg,eventArtworkSvg};
