const UFC_EVENTS_URL = "https://www.ufc.com/events?language_content_entity=en";
const UFC_ATHLETES_URL = "https://www.ufc.com/athletes/all";
const UFC_TTL_MS = Number(process.env.UFC_INTELLIGENCE_TTL_MS || 21600000);
let cache = { at: 0, athletes: new Map() };
const clean = v => String(v || "").replace(/\s+/g, " ").trim();
const key = v => clean(v).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const html = v => clean(String(v || "").replace(/<[^>]*>/g, " ").replace(/&amp;/g,"&").replace(/&#39;|&apos;/g,"'").replace(/&quot;/g,'"'));
async function fetchPage(url) { const r = await fetch(url,{headers:{accept:"text/html,application/xhtml+xml", "user-agent":"XSportsX/3.8"}}); if(!r.ok) throw new Error(`UFC ${r.status}`); return r.text(); }
function parseAthletes(body) {
  const map = new Map(); const re = /<a[^>]+href=["'](\/athlete\/[^"'#?]+)[^"']*["'][^>]*>([\s\S]*?)<\/a>/gi; let m;
  while ((m=re.exec(body))) { const profileUrl = new URL(m[1],"https://www.ufc.com").href; const name=html(m[2]); if(name) map.set(key(name),{name,profileUrl,official:true}); }
  return map;
}
async function load() { if(Date.now()-cache.at<UFC_TTL_MS && cache.athletes.size) return cache.athletes; try { const athletes=parseAthletes(await fetchPage(UFC_ATHLETES_URL)); cache={at:Date.now(),athletes}; return athletes; } catch { return cache.athletes; } }
export async function getFighterIntelligence(name, fallback={}) { const athletes=await load(); const found=athletes.get(key(name)); return {...fallback, name:clean(name)||fallback.name||"TBA", profileUrl:found?.profileUrl||fallback.profileUrl||"", official:Boolean(found?.official||fallback.official)}; }
function stat(v, fallback="—") { return v === undefined || v === null || v === "" ? fallback : v; }
function percent(v) { const n=Number(v); return Number.isFinite(n) ? `${Math.round(n)}%` : stat(v); }
function score(a,b,mode="high") { const x=Number(a), y=Number(b); if(!Number.isFinite(x)||!Number.isFinite(y)||x===y) return [false,false]; return mode==="low" ? [x<y,x>y] : [x>y,x<y]; }
export async function buildFightIntelligence(fight={}) {
  const [a,b]=await Promise.all([getFighterIntelligence(fight.fighter1?.name,fight.fighter1),getFighterIntelligence(fight.fighter2?.name,fight.fighter2)]);
  const comparison={
    records:[stat(a.record),stat(b.record)], ranks:[stat(a.rank,"Unranked"),stat(b.rank,"Unranked")],
    weightClass:fight.bout||"UFC", titleFight:Boolean(fight.title), rounds:Number(fight.rounds||3),
    physical:{height:[stat(a.height),stat(b.height)],reach:[stat(a.reach),stat(b.reach)],stance:[stat(a.stance),stat(b.stance)],weight:[stat(a.weight),stat(b.weight)]},
    offense:{koWins:[stat(a.koWins,0),stat(b.koWins,0)],submissionWins:[stat(a.submissionWins,0),stat(b.submissionWins,0)],sigStrikesPerMin:[stat(a.sigStrikesPerMin),stat(b.sigStrikesPerMin)],takedownsPer15:[stat(a.takedownsPer15),stat(b.takedownsPer15)],submissionsPer15:[stat(a.submissionsPer15),stat(b.submissionsPer15)]},
    defense:{sigStrikeDefense:[percent(a.sigStrikeDefense),percent(b.sigStrikeDefense)],takedownDefense:[percent(a.takedownDefense),percent(b.takedownDefense)]},
    recent:{lastFight:[stat(a.lastFight),stat(b.lastFight)],form:[stat(a.form),stat(b.form)]}
  };
  const [koA,koB]=score(a.koWins,b.koWins); const [subA,subB]=score(a.submissionWins,b.submissionWins); const [defA,defB]=score(a.sigStrikeDefense,b.sigStrikeDefense); comparison.edge={ko:[koA,koB],submission:[subA,subB],strikingDefense:[defA,defB]};
  return {...fight,fighter1:a,fighter2:b,comparison};
}
export async function buildEventIntelligence(detail={}) { const fights=await Promise.all((detail.fights||[]).map(buildFightIntelligence)); return {...detail,fights,intelligence:{officialSource:UFC_EVENTS_URL,mainEvent:fights.find(f=>f.mainEvent)||fights[0]||null,coMain:fights.find(f=>f.coMain)||fights[1]||null,titleFights:fights.filter(f=>f.title).length}}; }
export function renderFaceOff(fight={}) {
  const a=fight.fighter1||{}, b=fight.fighter2||{}, c=fight.comparison||{};
  return {title:`🥊 ${a.name||"Fighter A"} VS ${b.name||"Fighter B"}`,hero:{left:{name:a.name,rank:a.rank||"Unranked",image:a.image||"",record:a.record||"—",profileUrl:a.profileUrl||""},right:{name:b.name,rank:b.rank||"Unranked",image:b.image||"",record:b.record||"—",profileUrl:b.profileUrl||""}},sections:[{title:"⚔️ FIGHT INTELLIGENCE",rows:[{label:"Weight Class",a:c.weightClass,b:c.weightClass},{label:"Rounds",a:c.rounds,b:c.rounds},{label:"Title Fight",a:c.titleFight?"🏆 YES":"No",b:c.titleFight?"🏆 YES":"No"}]},{title:"📏 PHYSICAL",rows:["height","reach","stance","weight"].map((k,i)=>({label:k[0].toUpperCase()+k.slice(1),a:c.physical?.[k]?.[0]||"—",b:c.physical?.[k]?.[1]||"—"}))},{title:"💥 OFFENSE",rows:["koWins","submissionWins","sigStrikesPerMin","takedownsPer15","submissionsPer15"].map(k=>({label:k.replace(/([A-Z])/g," $1"),a:c.offense?.[k]?.[0]??"—",b:c.offense?.[k]?.[1]??"—"}))},{title:"🛡️ DEFENSE",rows:["sigStrikeDefense","takedownDefense"].map(k=>({label:k.replace(/([A-Z])/g," $1"),a:c.defense?.[k]?.[0]??"—",b:c.defense?.[k]?.[1]??"—"}))}]};
}
export const ufcIntelligenceVersion="3.8.1";
