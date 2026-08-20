import fs from "node:fs";

const file = new URL("./sports-router.js", import.meta.url);
let source = fs.readFileSync(file, "utf8");

const broken = 'async function resolveEventMeta(id){const h=await resolveEventMeta(id);if(h)return h;';
const fixed = 'async function resolveEventMeta(id){const cached=eventCache.get(id);if(cached)return cached;';

if (source.includes(broken)) {
  source = source.replace(broken, fixed);
  console.log("[XSportsX] Fixed recursive resolveEventMeta() before backend start.");
}

source = source.replace(
  /async function resolveEventMeta\(id\)\{\s*const h=await resolveEventMeta\(id\);\s*if\(h\)return h;/,
  'async function resolveEventMeta(id){const cached=eventCache.get(id);if(cached)return cached;'
);

// The original matcher could probe hundreds of IPTV channels with sequential EPG
// requests. That makes Nuvio sit on "Finding streams" for minutes. Keep EPG as a
// fallback, but only probe the best sports-channel candidates and fail quickly.
source = source.replace(').slice(0,500);', ').slice(0,24);');
source = source.replace('u.toString(),5000)', 'u.toString(),1800)');
source = source.replace('f.toString(),5000)', 'f.toString(),1800)');
source = source.replace('set("limit","20")', 'set("limit","10")');

fs.writeFileSync(file, source, "utf8");
console.log("[XSportsX] Startup patch applied: metadata recursion fixed and EPG probing bounded for fast Nuvio stream discovery.");
