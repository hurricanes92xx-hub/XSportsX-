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

fs.writeFileSync(file, source, "utf8");
console.log("[XSportsX] Sports router startup patch applied.");
