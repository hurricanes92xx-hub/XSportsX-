from pathlib import Path

hotfix = Path('hotfix-entry.js')
text = hotfix.read_text()

# Add WWE as a wrestling league without disturbing the existing ESPN leagues.
old = "boxing:['Boxing','boxing','boxing','🥊']}"
new = "boxing:['Boxing','boxing','boxing','🥊'],wwe:['WWE','wrestling','wwe','🤼']}"
if "wwe:['WWE','wrestling','wwe','🤼']" not in text:
    if old not in text:
        raise SystemExit('LEAGUES anchor not found')
    text = text.replace(old, new, 1)

# Pull the official WWE weekly/upcoming schedule page at runtime. The page is
# the authoritative source and contains both the current week and upcoming PLEs.
marker = "async function events(league){return cached(`events:${league}:${dateRange()}`,20000,async()=>{"
if "async function wweEvents()" not in text:
    if marker not in text:
        raise SystemExit('events() anchor not found')
    injected = r'''function decodeHtml(s){return String(s||'').replace(/&nbsp;/g,' ').replace(/&amp;/g,'&').replace(/&#39;/g,"'").replace(/&quot;/g,'"').replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim();}
function wweDateValue(s){const m=String(s||'').match(/(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(?:Jan\.?|Feb\.?|Mar\.?|Apr\.?|May|Jun\.?|Jul\.?|Aug\.?|Sep\.?|Oct\.?|Nov\.?|Dec\.?)\s+\d{1,2}(?:,)?\s+\d{4}/i);if(!m)return '';const d=new Date(m[0]);const tm=String(s||'').match(/\b(\d{1,2})(?::(\d{2}))?\s*(a\.m\.|p\.m\.|AM|PM)\b/i);if(tm){let h=Number(tm[1])%12;if(/p/i.test(tm[3]))h+=12;d.setHours(h,Number(tm[2]||0),0,0);}return Number.isNaN(d.getTime())?'':d.toISOString();}
async function wweEvents(){return cached('wwe:official-schedule',300000,async()=>{try{const html=await getJson('https://www.wwe.com/article/wwe-upcoming-events',7000).catch(async()=>{const r=await axios.get('https://www.wwe.com/article/wwe-upcoming-events',{timeout:7000,headers:{'User-Agent':`XSportsX/${VERSION}`,'Accept':'text/html'}});return r.data;});const cleanText=decodeHtml(html);const shows=['Raw on Netflix','NXT','WWE Evolve','WWE Main Event','Friday Night SmackDown',"Sunday Night's Main Event",'AAA Ola de Color & NXT Heatwave','AAA TripleMania 34 Night 1','AAA TripleMania 34 Night 2','WWE/NXT/AAA Worlds Collide','Money in the Bank 2026','Survivor Series: WarGames 2026'];const dates=[...cleanText.matchAll(/(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(?:Jan\.?|Feb\.?|Mar\.?|Apr\.?|May|Jun\.?|Jul\.?|Aug\.?|Sep\.?|Oct\.?|Nov\.?|Dec\.?)\s+\d{1,2}(?:,)?\s+\d{4}[^.]{0,260}/gi)];const out=[];for(const m of dates){const chunk=m[0],start=wweDateValue(chunk);if(!start)continue;const at=m.index||0;const before=cleanText.slice(Math.max(0,at-180),at);const show=shows.slice().sort((a,b)=>b.length-a.length).find(x=>before.toLowerCase().includes(x.toLowerCase()))||chunk.split(/,\s*(?:live|\d{1,2}\s*p\.m\.)/i)[0].trim();const title=show||'WWE Event';const id=crypto.createHash('sha1').update(`${title}|${start}`).digest('hex').slice(0,16);const state=new Date(start).getTime()<=Date.now()?'in':'pre';out.push({id,league:'wwe',leagueName:'WWE',start,state,home:{name:'WWE',short:'WWE',logo:'https://commons.wikimedia.org/wiki/Special:Redirect/file/WWE_official_logo.svg'},away:{name:title,short:title.slice(0,12),logo:'https://commons.wikimedia.org/wiki/Special:Redirect/file/WWE_official_logo.svg'},detail:chunk.replace(/^.*?\d{4}/,'').trim()||'Scheduled',broadcast:[],eventName:title,eventLogo:'https://commons.wikimedia.org/wiki/Special:Redirect/file/WWE_official_logo.svg'});}const seen=new Set();return out.filter(e=>{if(seen.has(e.id))return false;seen.add(e.id);return true;}).sort((a,b)=>new Date(a.start)-new Date(b.start));}catch{return[];}});}
'''
    text = text.replace(marker, injected + marker, 1)
    text = text.replace(marker, "async function events(league){if(league==='wwe')return wweEvents();return cached(`events:${league}:${dateRange()}`,20000,async()=>{", 1)

# Show the actual WWE event title instead of rendering a fake WWE-vs-WWE matchup.
old_meta = "name:`${e.leagueName} • ${e.away.short||e.away.name} vs ${e.home.short||e.home.name}`"
new_meta = "name:e.league==='wwe'?`${e.leagueName} • ${e.eventName||e.away.name}`:`${e.leagueName} • ${e.away.short||e.away.name} vs ${e.home.short||e.home.name}`"
if old_meta in text:
    text = text.replace(old_meta, new_meta, 1)

hotfix.write_text(text)

# Give WWE its own artwork theme so it never falls back to OTHER SPORTS.
art = Path('artwork.js')
a = art.read_text()
old_theme = "boxing:['BOXING','#ff1738','COMBAT SPORTS'],other:['OTHER SPORTS'"
new_theme = "boxing:['BOXING','#ff1738','COMBAT SPORTS'],wwe:['WWE','#d4d7dc','WRESTLING'],other:['OTHER SPORTS'"
if "wwe:['WWE'" not in a:
    if old_theme not in a:
        raise SystemExit('artwork theme anchor not found')
    a = a.replace(old_theme, new_theme, 1)
art.write_text(a)

print('WWE official schedule patch applied')
