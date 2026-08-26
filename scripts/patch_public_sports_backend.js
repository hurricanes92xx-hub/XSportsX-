const fs = require('fs');

const LEAGUES = `const LEAGUES={
 nfl:['NFL','football','nfl','🏈'],ncaaf:['NCAA Football','football','college-football','🏈'],
 nba:['NBA','basketball','nba','🏀'],wnba:['WNBA','basketball','wnba','🏀'],ncaab:['NCAA Basketball','basketball','mens-college-basketball','🏀'],
 mlb:['MLB','baseball','mlb','⚾'],nhl:['NHL','hockey','nhl','🏒'],
 mls:['MLS','soccer','usa.1','⚽'],epl:['Premier League','soccer','eng.1','⚽'],ucl:['UEFA Champions League','soccer','uefa.champions','⚽'],
 laliga:['LaLiga','soccer','esp.1','⚽'],seriea:['Serie A','soccer','ita.1','⚽'],bundesliga:['Bundesliga','soccer','ger.1','⚽'],ligue1:['Ligue 1','soccer','fra.1','⚽'],
 ufc:['UFC','mma','ufc','🥊'],boxing:['Boxing','boxing','boxing','🥊'],
 rugby:['Rugby','rugby','rugby','🏉'],volleyball:['Volleyball','volleyball','volleyball','🏐'],lacrosse:['Lacrosse','lacrosse','lacrosse','🥍'],
 wrestling:['Wrestling','wrestling','wrestling','🤼'],judo:['Judo','combat','judo','🥋'],taekwondo:['Taekwondo','combat','taekwondo','🥋'],
 swimming:['Swimming','swimming','swimming','🏊'],diving:['Diving','swimming','diving','🤿'],waterpolo:['Water Polo','water-polo','water-polo','🤽'],
 gymnastics:['Gymnastics','gymnastics','gymnastics','🤸'],cycling:['Cycling','cycling','cycling','🚴'],darts:['Darts','darts','darts','🎯'],
 snooker:['Snooker','snooker','snooker','🎱'],archery:['Archery','archery','archery','🏹'],equestrian:['Equestrian','equestrian','equestrian','🐎'],
 handball:['Handball','handball','handball','🤾'],fieldhockey:['Field Hockey','field-hockey','field-hockey','🏑'],cricket:['Cricket','cricket','cricket','🏏'],
 monsterjam:['Monster Jam','motorsports','monster-jam','🚛'],motogp:['MotoGP','motorsport','motogp','🏍️'],wrc:['WRC','motorsport','wrc','🏁'],wec:['WEC','motorsport','wec','🏎️'],imsa:['IMSA','motorsport','imsa','🏎️'],formulae:['Formula E','motorsport','formula-e','🏎️'],mxgp:['MXGP','motorsport','mxgp','🏍️'],esports:['Esports','esports','esports','🎮']
};`;
const SPORT_RE = String.raw`const SPORT_RE=/\b(sport|sports|espn|espn\+|fox sports|fs1|fs2|tnt|nba|mlb|nhl|nfl|ncaaf|ncaab|wnba|sec network|acc network|big ten|bally|msg|regional sports|baseball|basketball|football|hockey|soccer|tennis|golf|cbs sports|nbc sports|bein|sky sport|f1|formula|racing|ufc|boxing|fight|paramount|tsn|sportsnet|peacock|fanatiz|rugby|volleyball|lacrosse|wrestling|judo|taekwondo|swimming|diving|water polo|gymnastics|cycling|darts|snooker|archery|equestrian|handball|field hockey|cricket|monster jam|motogp|wrc|wec|imsa|formula e|mxgp|esports|gaming)\b/i;`;
const ALIASES = `const SPORT_ALIASES={
 nfl:['nfl','football'],ncaaf:['ncaaf','ncaa football','college football','college-football'],nba:['nba'],wnba:['wnba'],ncaab:['ncaab','ncaa basketball','college basketball','mens-college-basketball'],mlb:['mlb'],nhl:['nhl'],mls:['mls'],epl:['epl','premier league','english premier league'],ucl:['ucl','uefa champions league','champions league'],laliga:['laliga','la liga'],seriea:['seriea','serie a'],bundesliga:['bundesliga'],ligue1:['ligue1','ligue 1'],ufc:['ufc','mma'],boxing:['boxing','box'],
 rugby:['rugby','rugby union','rugby sevens','rugby league'],volleyball:['volleyball','beach volleyball'],lacrosse:['lacrosse'],wrestling:['wrestling','grappling'],judo:['judo'],taekwondo:['taekwondo'],swimming:['swimming'],diving:['diving'],waterpolo:['water polo','waterpolo'],gymnastics:['gymnastics','artistic gymnastics','rhythmic gymnastics'],cycling:['cycling','road cycling','track cycling','mountain bike','bmx'],darts:['darts'],snooker:['snooker','pool','billiards'],archery:['archery'],equestrian:['equestrian','show jumping','dressage','eventing'],handball:['handball'],fieldhockey:['field hockey'],cricket:['cricket'],monsterjam:['monster jam'],motogp:['motogp','moto gp'],wrc:['wrc','world rally championship'],wec:['wec','world endurance championship'],imsa:['imsa'],formulae:['formula e','formula-e'],mxgp:['mxgp'],esports:['esports','gaming']
};
function selectedLeagueSet(c){const raw=Array.isArray(c?.sports)?c.sports:[];if(!raw.length)return new Set();const out=new Set();for(const v of raw){const x=String(v||'').trim().toLowerCase();for(const [id,a] of Object.entries(SPORT_ALIASES))if(a.includes(x)){out.add(id);break;}}return out;}`;
const SOURCES = `const OFFICIAL_SOURCES={rugby:['RugbyPass TV','https://www.rugbypass.tv/'],monsterjam:['Monster Jam','https://www.monsterjam.com/en-us/watch/'],motogp:['MotoGP','https://www.youtube.com/@MotoGP'],wrc:['FIA World Rally Championship','https://www.youtube.com/@WorldRallyChampionship'],wec:['FIA WEC','https://www.youtube.com/@FIAWEC'],imsa:['IMSA','https://www.youtube.com/@IMSAOfficial'],formulae:['Formula E','https://www.youtube.com/@FIAFormulaE'],mxgp:['MXGP','https://www.youtube.com/@mxgptv'],esports:['Red Bull TV','https://www.redbull.com/us-en/live-events']};
function sourceForLeague(k){const x=OFFICIAL_SOURCES[k];return x?{name:x[0],url:x[1]}:null;}`;

function patchServer() {
  let s=fs.readFileSync('server.js','utf8');
  if (s.includes('// XSportsX public sports backend v2')) return;
  s=s.replace(/const LEAGUES=\{[\s\S]*?\n\};/, LEAGUES);
  s=s.replace(/const SPORT_RE=.*?;/s, SPORT_RE);
  s=s.replace(/function selectedLeagueSet\(c\)\{[\s\S]*?\nfunction config/, ALIASES+'\nfunction config');
  const marker="function scoreboardUrl(k){const l=LEAGUES[k];return l?`https://site.api.espn.com/apis/site/v2/sports/${l[1]}/${l[2]}/scoreboard?dates=${dateRange()}&limit=100`:'';}";
  if (s.includes(marker)) s=s.replace(marker, marker+'\n'+SOURCES);
  s=s.replace("genres:['Sports',e.leagueName],sportSource:e.league,eventId:e.id,event:e,behaviorHints:{isPlayable:true}", "genres:['Sports',e.leagueName],sportSource:e.league,eventId:e.id,event:e,officialSource:sourceForLeague(e.league),behaviorHints:{isPlayable:true}");
  fs.writeFileSync('server.js','// XSportsX public sports backend v2\n'+s);
}
function patchBootstrap() {
  let s=fs.readFileSync('bootstrap.js','utf8');
  if (s.includes('// XSportsX public sports backend v2')) return;
  s=s.replace(/const LEAGUES=\{[\s\S]*?\n\};/, LEAGUES);
  fs.writeFileSync('bootstrap.js','// XSportsX public sports backend v2\n'+s);
}
patchServer();
patchBootstrap();
console.log('XSportsX public sports backend v2 applied');
