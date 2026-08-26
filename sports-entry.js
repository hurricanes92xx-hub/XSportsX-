const fs=require('fs');
const path=require('path');

const target=path.join(__dirname,'hotfix-entry.js');
let source=fs.readFileSync(target,'utf8');
const start=source.indexOf('const LEAGUES={');
const end=source.indexOf('\n};\nconst SPORT=',start);
if(start<0||end<0)throw new Error('Unable to locate hotfix LEAGUES registry');

// Only enable leagues with a documented public ESPN scoreboard endpoint.
// Sports without a reliable scoreboard feed remain available through the
// remote catalog/source-discovery layer instead of producing empty/fake events.
const expanded=`const LEAGUES={
  nfl:['NFL','football','nfl','🏈'],
  ncaaf:['NCAA Football','football','college-football','🏈'],
  nba:['NBA','basketball','nba','🏀'],
  wnba:['WNBA','basketball','wnba','🏀'],
  ncaab:['NCAA Basketball','basketball','mens-college-basketball','🏀'],
  mlb:['MLB','baseball','mlb','⚾'],
  nhl:['NHL','hockey','nhl','🏒'],
  mls:['MLS','soccer','usa.1','⚽'],
  epl:['Premier League','soccer','eng.1','⚽'],
  ucl:['UEFA Champions League','soccer','uefa.champions','⚽'],
  laliga:['LaLiga','soccer','esp.1','⚽'],
  seriea:['Serie A','soccer','ita.1','⚽'],
  bundesliga:['Bundesliga','soccer','ger.1','⚽'],
  ligue1:['Ligue 1','soccer','fra.1','⚽'],
  ufc:['UFC','mma','ufc','🥊'],
  boxing:['Boxing','boxing','boxing','🥊'],
  f1:['Formula 1','racing','f1','🏎️'],
  nascar:['NASCAR Cup','racing','nascar-premier','🏁'],
  indycar:['IndyCar','racing','irl','🏎️'],
  rugby_six:['Six Nations Rugby','rugby','180659','🏉'],
  rugby_world:['Rugby World Cup','rugby','164205','🏉'],
  rugby_nrl:['NRL Rugby League','rugby-league','3','🏉'],
  lacrosse_pll:['Premier Lacrosse League','lacrosse','pll','🥍'],
  lacrosse_nll:['National Lacrosse League','lacrosse','nll','🥍'],
  volleyball_w:['NCAA Women’s Volleyball','volleyball','womens-college-volleyball','🏐'],
  volleyball_m:['NCAA Men’s Volleyball','volleyball','mens-college-volleyball','🏐'],
  afl:['Australian Football','australian-football','afl','🏉'],
  cricket_ipl:['IPL Cricket','cricket','ipl','🏏'],
  cricket_t20:['ICC T20 Cricket','cricket','icc.t20','🏏']
};`;
source=source.slice(0,start)+expanded+source.slice(end+3);
// Execute the production hotfix entry after replacing only its in-memory league registry.
// The original hotfix-entry.js remains untouched for easy rollback/audit.
const runner=new Function('require','process','__dirname','__filename',source);
runner(require,process,__dirname,target);
