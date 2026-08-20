// Render/Nuvio production gateway.
// v526 owns the public listener and proxies catalog/meta/stream requests
// to the stable backend while generating absolute Nuvio manifest URLs.
await import("./render-entry-v526.js");
