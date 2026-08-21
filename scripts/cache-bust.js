const fs = require('node:fs');
const path = require('node:path');

const file = path.join(process.cwd(), 'server.js');
let src = fs.readFileSync(file, 'utf8');
const version = '20260821-6';

const beforeUrl = "function eventArtworkUrl(req,e){return `${baseUrl(req)}/artwork/event/${encodeURIComponent(e.league)}/${encodeURIComponent(e.id)}.png`}";
const afterUrl = "function eventArtworkUrl(req,e){return `${baseUrl(req)}/artwork/event/${encodeURIComponent(e.league)}/${encodeURIComponent(e.id)}.png?v=20260821-6`}";

if (src.includes(beforeUrl)) {
  src = src.replace(beforeUrl, afterUrl);
} else {
  console.log('cache-bust: event artwork URL already versioned');
}

src = src.replace(
  "res.type('image/png').set('Cache-Control','public, max-age=300').set('X-XSportsX-Art','raster-v2').send(png)",
  "res.type('image/png').set('Cache-Control','no-store, max-age=0').set('X-XSportsX-Art',version).send(png)"
);

fs.writeFileSync(file, src);
console.log(`cache-bust: poster artwork version ${version}`);
