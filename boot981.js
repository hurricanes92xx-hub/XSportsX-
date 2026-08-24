const fs=require('fs');
const Module=require('module');
const path=require('path');
const source=fs.readFileSync(path.join(__dirname,'app98.js'),'utf8')
  .replace("const VERSION='9.8.0'", "const VERSION='9.8.1'")
  .replace("id:'community.xsportsx'", "id:'community.xsportsx981'");
const m=new Module(path.join(__dirname,'app98.js'),module);
m.filename=path.join(__dirname,'app98.js');
m.paths=module.paths;
m._compile(source,m.filename);
