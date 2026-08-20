import http from "node:http";
import { spawn } from "node:child_process";

const PUBLIC_PORT=Number(process.env.PORT||7000);
const INTERNAL_PORT=Number(process.env.XSPORTSX_INTERNAL_PORT||7099);
const PREFIX="v458";
const BASE="http://127.0.0.1:"+INTERNAL_PORT;

const child=spawn(process.execPath,["command-center.js"],{
  env:{...process.env,PORT:String(INTERNAL_PORT)},
  stdio:"inherit"
});
child.on("error",e=>console.error("XSportsX internal server failed:",e));
child.on("exit",code=>{console.error(`XSportsX internal server exited: ${code}`);process.exit(code||1);});

function decodePart(value){
  try{return decodeURIComponent(value);}catch{return value;}
}

function proxyPath(original){
  const u=new URL(original,"http://localhost");
  const parts=u.pathname.split("/").filter(Boolean);
  const i=parts.indexOf(PREFIX);
  if(i<0)return {path:u.pathname,query:u.search};
  const rest=parts.slice(i+1);
  if(!rest.length)return {path:"/manifest.json",query:""};
  if(rest[0]==="configure"||rest[0]==="manifest.json"||rest[0]==="health")return {path:"/"+rest[0],query:u.search};
  const token=decodePart(rest[0]);
  const resource=rest.slice(1).map(decodePart);
  const q=new URLSearchParams(u.search);
  q.set("config",token);
  return {path:"/"+resource.join("/"),query:q.toString()?"?"+q.toString():""};
}

const server=http.createServer((req,res)=>{
  try{
    const p=proxyPath(req.url||"/");
    const target=new URL(p.path+p.query,BASE);
    const upstream=http.request(target,{method:req.method,headers:{...req.headers,host:`127.0.0.1:${INTERNAL_PORT}`,connection:"keep-alive"}},ur=>{
      const headers={...ur.headers,"cache-control":ur.headers["cache-control"]||"no-store","x-xsportsx-proxy":"v458"};
      res.writeHead(ur.statusCode||502,headers);
      ur.pipe(res);
    });
    upstream.on("error",e=>{if(!res.headersSent){res.writeHead(502,{"content-type":"application/json"});}res.end(JSON.stringify({error:"XSportsX upstream unavailable",detail:String(e.message||e)}));});
    req.pipe(upstream);
  }catch(e){res.writeHead(502,{"content-type":"application/json"});res.end(JSON.stringify({error:String(e.message||e)}));}
});
server.keepAliveTimeout=120000;
server.headersTimeout=125000;
server.requestTimeout=120000;
server.listen(PUBLIC_PORT,"0.0.0.0",()=>console.log(`XSportsX proxy listening on ${PUBLIC_PORT}; internal on ${INTERNAL_PORT}`));
