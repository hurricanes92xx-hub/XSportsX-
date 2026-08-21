// Stable boot shim.
// Patch the source-manager discovery function before the production gateway imports it.
// This keeps the existing sports gateway intact while fixing decoded-source discovery.
import fs from "node:fs";

const target = new URL("./render-entry-v528.js", import.meta.url);
let source = fs.readFileSync(target, "utf8");

if (!source.includes("XSX_SOURCE_DISCOVERY_V2")) {
  const marker = "async function getSourceStateByToken(token){";
  const endMarker = "}\nconst configureHtml=";
  const start = source.indexOf(marker);
  const end = source.indexOf(endMarker, start);

  if (start < 0 || end < 0) {
    throw new Error("XSportsX source discovery patch target not found");
  }

  const replacement = `// XSX_SOURCE_DISCOVERY_V2
function xsxSafeSourceUrl(raw){
  try{
    const u=new URL(String(raw||""));
    if(!/^https?:$/.test(u.protocol))return null;
    for(const k of ["username","password","user","pass"]){
      if(u.searchParams.has(k))u.searchParams.set(k,"[hidden]");
    }
    return u.toString();
  }catch{return null}
}
function xsxSourceUrls(text){
  return [...new Set((String(text||"").match(/https?:\\/\\/[^\\s"'<>]+/gi)||[])
    .map(x=>x.replace(/[\\]\\[),;]+$/g,""))
    .filter(Boolean))];
}
async function getSourceStateByToken(token){
  if(!token)return null;
  const state=loadSourceState(token);
  const config=decryptConfig("/${PUBLIC_PREFIX}/"+encodeURIComponent(token)+"/manifest.json");
  const diagnostics={postsChecked:0,base64Decoded:0,destinationsFetched:0,m3u:0,xtream:0,stalker:0,credentialedRecords:0};

  if(config?.sourceUrl){
    try{
      const scan=await scanBase64Input({site:config.sourceUrl,health:true});
      diagnostics.base64Decoded=Array.isArray(scan.decoded)?scan.decoded.length:0;
      const candidates=[];
      for(const x of (scan.links||[]))candidates.push({url:x.url,healthy:Boolean(x.ok),status:x.status,latencyMs:x.latencyMs,details:"Discovered from authorized source"});
      for(const d of (scan.decoded||[])){
        for(const u of xsxSourceUrls(d.text))candidates.push({url:u,healthy:false,details:"Discovered inside decoded source"});
      }
      for(const c of candidates){
        const raw=String(c.url||"");
        let parsed;
        try{parsed=new URL(raw)}catch{continue}
        const path=parsed.pathname.toLowerCase();
        const q=parsed.searchParams;
        const hasCred=q.has("username")||q.has("password")||q.has("user")||q.has("pass");
        let type="direct";
        if((q.get("type")||"").toLowerCase().includes("m3u")||path.includes("/get.php")||path.includes(".m3u"))type="m3u";
        else if(path.includes("player_api.php"))type="xtream";
        else if(path.includes("/portal.php")||path.includes("stalker"))type="stalker";
        if(type==="direct"&&!/\\.(m3u8?|mpd)(?:$|[?#])/i.test(path)&&!/(iptv|stream|live)/i.test(raw))continue;
        diagnostics.destinationsFetched++;
        diagnostics[type]=(diagnostics[type]||0)+1;
        if(hasCred)diagnostics.credentialedRecords++;
        const safe=xsxSafeSourceUrl(raw);
        if(!safe)continue;
        const item={url:safe,type,healthy:Boolean(c.healthy),status:c.status,latencyMs:c.latencyMs,details:hasCred?("IPTV "+type.toUpperCase()+" record found • credentials protected"):"Discovered "+type.toUpperCase()+" source"};
        if(state.approved.some(a=>a.url===safe)||state.rejected.includes(safe))continue;
        if(!state.pending.some(a=>a.url===safe))state.pending.push(item);
      }
    }catch(e){console.error("Source discovery failed:",e.message)}
  }

  if(config?.subreddit){
    try{
      const result=await scanSubreddit(config.subreddit,{maxPosts:100});
      Object.assign(diagnostics,result.diagnostics||{});
      diagnostics.postsChecked=result.postsChecked||diagnostics.postsChecked||0;
      for(const x of (result.discoveries||[])){
        const safe=xsxSafeSourceUrl(x.url);
        if(!safe)continue;
        if(state.approved.some(a=>a.url===safe)||state.rejected.includes(safe)||state.pending.some(a=>a.url===safe))continue;
        state.pending.push({...x,url:safe,healthy:Boolean(x.healthy)});
      }
    }catch(e){console.error("Reddit source discovery failed:",e.message)}
  }

  state.pending=state.pending.slice(-500);
  const saved=saveSourceState(token,state);
  return {...saved,diagnostics};
}
`;

  // Replace through the old function's closing brace, not before it.
  source = source.slice(0,start) + replacement + source.slice(end + 1);
  fs.writeFileSync(target, source, "utf8");
  console.log("[XSportsX] source discovery patch applied");
}

console.log("[XSportsX] stable boot shim loaded");
