const fs = require('node:fs');
const path = require('node:path');

const file = path.join(process.cwd(), 'server.js');
let src = fs.readFileSync(file, 'utf8');
const version = '20260821-7';

const beforeUrl = "function eventArtworkUrl(req,e){return `${baseUrl(req)}/artwork/event/${encodeURIComponent(e.league)}/${encodeURIComponent(e.id)}.png`}";
const afterUrl = "function eventArtworkUrl(req,e){return `${baseUrl(req)}/artwork/event-v7/${encodeURIComponent(e.league)}/${encodeURIComponent(e.id)}.png`}";
if (src.includes(beforeUrl)) src = src.replace(beforeUrl, afterUrl);

// Tell Nuvio this is a landscape poster and keep the generated PNG compact.
src = src.replace(
  "poster:eventArtworkUrl(req,event),background:eventArtworkUrl(req,event),",
  "poster:eventArtworkUrl(req,event),background:eventArtworkUrl(req,event),posterShape:'landscape',"
);
src = src.replace(
  ".png().toBuffer();res.type('image/png')",
  ".png({compressionLevel:9,palette:true,quality:72}).toBuffer();res.type('image/png')"
);

src = src.replace(
  "res.type('image/png').set('Cache-Control','public, max-age=300').set('X-XSportsX-Art','raster-v2').send(png)",
  "res.type('image/png').set('Cache-Control','no-store, max-age=0').set('X-XSportsX-Art',version).send(png)"
);
fs.writeFileSync(file, src);
console.log(`cache-bust: poster artwork version ${version}`);
