// Render/Nuvio entrypoint. The proxy owns the public listener and forwards
// personalized catalog/meta/stream requests to the command-center service.
await import("./render-proxy.js");
