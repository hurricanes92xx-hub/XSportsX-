const fs = require('fs');
const path = require('path');
const appPath = path.join(__dirname, 'app.js');
let source = fs.readFileSync(appPath, 'utf8');
const bad = "return json(res,200,{ok:true,version:VERSION})}if(req.method==='GET'&&u.pathname==='/artwork.svg')";
const good = "return json(res,200,{ok:true,version:VERSION});if(req.method==='GET'&&u.pathname==='/artwork.svg')";
if (source.includes(bad)) source = source.replace(bad, good);
fs.writeFileSync(appPath, source);
require(appPath);
