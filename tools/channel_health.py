#!/usr/bin/env python3
"""Lightweight health checker for approved public HLS/M3U sources.

Only checks URLs supplied by the XSportsX public registry. It never discovers
or follows arbitrary third-party links.
"""
import json, ssl, sys, time
from urllib.parse import urlparse
from urllib.request import Request, urlopen

REGISTRY = "public-sources-registry.json"
TIMEOUT = 4
ALLOWED = ("https",)

def allowed(url):
    try:
        p=urlparse(url)
        return p.scheme in ALLOWED and p.hostname and any(
            p.hostname == h or p.hostname.endswith("."+h)
            for h in ("iptv-org.github.io","raw.githubusercontent.com","cdn.jsdelivr.net","wurl.com","amagi.tv","tubi.video","akamaized.net","github.io")
        )
    except Exception:
        return False

def check(url):
    if not allowed(url): return {"status":"blocked","score":0}
    start=time.monotonic()
    try:
        req=Request(url,headers={"User-Agent":"XSportsX-health/1.0","Accept":"application/vnd.apple.mpegurl,application/x-mpegURL,video/*,*/*"})
        with urlopen(req,timeout=TIMEOUT,context=ssl.create_default_context()) as r:
            data=r.read(65536)
            code=getattr(r,"status",200)
            ctype=r.headers.get("content-type","")
        latency=round((time.monotonic()-start)*1000)
        if code < 200 or code >= 300 or not data:
            return {"status":"offline","score":0,"latencyMs":latency}
        text=data.decode("utf-8","ignore")
        hls="#EXTM3U" in text
        score=70 if hls else 45
        if latency < 500: score += 20
        elif latency < 1200: score += 10
        return {"status":"healthy" if hls else "degraded","score":min(score,100),"latencyMs":latency,"hls":hls,"contentType":ctype}
    except Exception as e:
        return {"status":"offline","score":0,"error":type(e).__name__}

def main():
    with open(REGISTRY,encoding="utf-8") as f: reg=json.load(f)
    out={"version":1,"checkedAt":int(time.time()),"channels":[]}
    # This worker intentionally validates registry playlist endpoints, not every
    # channel URL, to avoid hammering public providers. The APK performs the
    # final per-stream check at selection time.
    for source in reg.get("sources",[]):
        if not source.get("enabled") or not source.get("public"): continue
        result=check(source.get("playlist",""))
        out["channels"].append({"sourceId":source.get("id"),"name":source.get("name"),**result})
    print(json.dumps(out,indent=2))

if __name__ == "__main__": main()
