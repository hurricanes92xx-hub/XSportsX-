const fs = require('fs');

const path = 'app96.js';
let source = fs.readFileSync(path, 'utf8');

source = source.replace(/const VERSION = ['\"]9\.6\.0['\"]/, "const VERSION = '9.7.0'");
source = source.replace(/XSportsX\/9\.6/g, 'XSportsX/9.7');

fs.writeFileSync(path, source);
console.log('XSportsX runtime version patched to 9.7.0');
