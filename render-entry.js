import { spawn } from "node:child_process";

// Render historically launched this file directly. The old implementation
// was pinned to 4.3.3 and bypassed the current 4.4.x production gateway.
// Keep render-entry as a compatibility launcher, but make it execute the
// canonical production gateway so Nuvio sees the same manifest everywhere.
const gatewayPort = Number(process.env.XSPORTSX_GATEWAY_PORT || 7002);
const backendPort = Number(process.env.XSPORTSX_BACKEND_PORT || 7001);

const gateway = spawn(process.execPath, ["gateway.js"], {
  env: {
    ...process.env,
    PORT: String(gatewayPort),
    XSPORTSX_BACKEND_PORT: String(backendPort)
  },
  stdio: "inherit"
});

gateway.on("exit", code => {
  if (code && code !== 0) process.exitCode = code;
});

// production-entry.js is the canonical 4.4.2 manifest/EPG gateway.
// Point it at the gateway we just started instead of its standalone default.
process.env.XSPORTSX_PRODUCTION_UPSTREAM_PORT = String(gatewayPort);
await import("./production-entry.js");
