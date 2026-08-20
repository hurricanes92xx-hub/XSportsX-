import fs from "node:fs";
import { spawn } from "node:child_process";

const file = "/app/sports-router.js";
let source = fs.readFileSync(file, "utf8");

// Keep the live Docker build deterministic. The previous build generated a new
// encryption key on every restart, which invalidated existing Nuvio config URLs.
source = source.replace(
  'const VERSION="5.0.19";',
  'const VERSION="5.0.20";'
);
source = source.replace(
  'const ADDON_ID="com.xsportsx.sports.epg.v516";',
  'const ADDON_ID="com.xsportsx.sports.epg.v520";'
);
source = source.replace(
  'const SECRET=process.env.XSPORTSX_CONFIG_SECRET||crypto.randomBytes(32).toString("hex");',
  'const SECRET=process.env.XSPORTSX_CONFIG_SECRET||"xsportsx-v520-stable-config-key";'
);

// The News catalog must remain visible even before Xtream credentials are
// available; streams still require the authorized Xtream configuration.
source = source.replace(
  'if(path.includes("/catalog/channel/sports-news-v2.json")||path.includes("/catalog/channel/sports-news.json")){if(!c)return json(res,{metas:[]});return json(res,{metas:(await xtreamData(c)).newsGroups},200,30)}',
  'if(path.includes("/catalog/channel/sports-news-v2.json")||path.includes("/catalog/channel/sports-news.json")){const fallback=Object.keys(NEWS_GROUPS).map(group=>({id:`news:${slug(group)}`,type:"channel",name:group,poster:newsLogo(group),background:newsLogo(group),description:`${group} • Xtream sports news`,genres:["Sports News",group],behaviorHints:{isLive:true},newsGroup:group}));if(!c)return json(res,{metas:[...fallback,{id:"news:sports-news",type:"channel",name:"Sports News",poster:newsLogo("Sports News"),background:newsLogo("Sports News"),description:"Sports News from your authorized Xtream provider",genres:["Sports News","News"],behaviorHints:{isLive:true},newsGroup:"__ALL_SPORTS_NEWS__"}]},200,30);return json(res,{metas:(await xtreamData(c)).newsGroups},200,30)}'
);

fs.writeFileSync(file, source);
const child = spawn(process.execPath, ["render-proxy.js"], { stdio: "inherit", env: process.env });
child.on("exit", code => process.exit(code ?? 1));
child.on("error", err => { console.error(err); process.exit(1); });
