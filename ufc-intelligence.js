const UFC_EVENTS_URL = "https://www.ufc.com/events?language_content_entity=en";
const UFC_ATHLETES_URL = "https://www.ufc.com/athletes/all";
const UFC_TTL_MS = Number(process.env.UFC_INTELLIGENCE_TTL_MS || 900000);
let cache = { at: 0, athletes: new Map() };
const clean = v => String(v || "").replace(/\s+/g, " ").trim();
const key = v => clean(v).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const html = v => clean(String(v || "").replace(/<[^>]*>/g, " ").replace(/&amp;/g,"&").replace(/&#39;|&apos;/g,"'").replace(/&quot;/g,'"'));
async function fetchPage(url) { const r = await fetch(url,{headers:{accept:"text/html,application/xhtml+xml", "user-agent":"XSportsX/3.7"}}); if(!r.ok) throw new Error(`UFC ${r.status}`); return r.text(); }
function parseAthletes(body) {
  const map = new Map(); const re = /<a[^>]+href=["'](\/athlete\/[^"'#?]+)[^"']*["'][^>]*>([\s\S]*?)<\/a>/gi; let m;
  while ((m=re.exec(body))) { const profileUrl = new URL(m[1],"https://www.ufc.com").href; const name=html(m[2]); if(name) map.set(key(name),{name,profileUrl,official:true}); }
  return map;
}
async function load() { if(Date.now()-cache.at<UFC_TTL_MS && cache.athletes.size) return cache.athletes; try { const athletes=parseAthletes(await fetchPage(UFC_ATHLETES_URL)); cache={at:Date.now(),athletes}; return athletes; } catch { return cache.athletes; } }
export async function getFighterIntelligence(name, fallback={}) { const athletes=await load(); const found=athletes.get(key(name)); return {...fallback, name:clean(name)||fallback.name||"TBA", profileUrl:found?.profileUrl||fallback.profileUrl||"", official:Boolean(found?.official||fallback.official)}; }
export async function buildFightIntelligence(fight={}) { const [a,b]=await Promise.all([getFighterIntelligence(fight.fighter1?.name,fight.fighter1),getFighterIntelligence(fight.fighter2?.name,fight.fighter2)]); return {...fight,fighter1:a,fighter2:b,comparison:{records:[a.record||"—",b.record||"—"],ranks:[a.rank||"Unranked",b.rank||"Unranked"],weightClass:fight.bout||"UFC",titleFight:Boolean(fight.title),rounds:Number(fight.rounds||3)}}; }
export async function buildEventIntelligence(detail={}) { const fights=await Promise.all((detail.fights||[]).map(buildFightIntelligence)); return {...detail,fights,intelligence:{officialSource:UFC_EVENTS_URL,mainEvent:fights.find(f=>f.mainEvent)||fights[0]||null,coMain:fights.find(f=>f.coMain)||null,titleFights:fights.filter(f=>f.title).length}}; }
export const ufcIntelligenceVersion="3.8.0";
