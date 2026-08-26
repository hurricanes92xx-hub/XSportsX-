#!/usr/bin/env python3
"""Batch health scanner for approved public M3U sources.

Scans a bounded batch each run and persists a compact per-channel snapshot.
It only follows URLs from the approved registry and never discovers arbitrary
third-party links.
"""
import json, os, ssl, time
from urllib.parse import urlparse
from urllib.request import Request, urlopen

REGISTRY = "public-sources-registry.json"
STATE = "docs/public-channel-health.json"
TIMEOUT = 4
BATCH_SIZE = int(os.getenv("HEALTH_BATCH_SIZE", "80"))
MAX_PLAYLIST_BYTES = 12_000_000
ALLOWED_HOSTS = ("iptv-org.github.io","raw.githubusercontent.com","cdn.jsdelivr.net","wurl.com","amagi.tv","tubi.video","akamaized.net","github.io")


def allowed(url):
    try:
        p = urlparse(url)
        return p.scheme == "https" and p.hostname and any(p.hostname == h or p.hostname.endswith("." + h) for h in ALLOWED_HOSTS)
    except Exception:
        return False


def fetch(url, limit=MAX_PLAYLIST_BYTES):
    if not allowed(url): return None
    try:
        req = Request(url, headers={"User-Agent":"XSportsX-health/1.1","Accept":"application/vnd.apple.mpegurl,application/x-mpegURL,text/plain,*/*"})
        with urlopen(req, timeout=TIMEOUT, context=ssl.create_default_context()) as r:
            data = r.read(limit + 1)
            if getattr(r, "status", 200) < 200 or getattr(r, "status", 200) >= 300 or len(data) > limit:
                return None
            return data.decode("utf-8", "ignore")
    except Exception:
        return None


def attr(line, key):
    import re
    m = re.search(rf'{key}="([^"]*)"', line, re.I)
    return m.group(1) if m else ""


def parse_m3u(text, source_id, source_name):
    import re
    out=[]; name=""; group="LIVE"; logo=""
    for line in text.splitlines():
        v=line.strip()
        if v.upper().startswith("#EXTINF"):
            name=v.split(",",1)[-1].strip() or "Unnamed"
            group=attr(v,"group-title") or "LIVE"
            logo=attr(v,"tvg-logo")
        elif v and not v.startswith("#"):
            if name and allowed(v):
                out.append({"id":f"{source_id}:{v}","sourceId":source_id,"sourceName":source_name,"name":name,"group":group,"logo":logo,"url":v})
            name=""; group="LIVE"; logo=""
    return out


def health(url):
    if not allowed(url): return {"status":"blocked","score":0}
    started=time.monotonic()
    try:
        req=Request(url,headers={"User-Agent":"XSportsX-health/1.1","Accept":"application/vnd.apple.mpegurl,application/x-mpegURL,video/*,*/*"})
        with urlopen(req,timeout=TIMEOUT,context=ssl.create_default_context()) as r:
            data=r.read(65536); code=getattr(r,"status",200); ctype=r.headers.get("content-type","")
        latency=round((time.monotonic()-started)*1000)
        if code < 200 or code >= 300 or not data: return {"status":"offline","score":0,"latencyMs":latency}
        text=data.decode("utf-8","ignore")
        if "#EXTM3U" not in text and "video" not in ctype.lower(): return {"status":"degraded","score":35,"latencyMs":latency}
        score=80 if "#EXTM3U" in text else 60
        score += 20 if latency < 500 else 10 if latency < 1200 else 0
        return {"status":"healthy" if score >= 80 else "degraded","score":min(score,100),"latencyMs":latency}
    except Exception as e:
        return {"status":"offline","score":0,"error":type(e).__name__}


def main():
    with open(REGISTRY, encoding="utf-8") as f: reg=json.load(f)
    state={"version":2,"updatedAt":int(time.time()),"cursor":0,"channels":{}}
    if os.path.exists(STATE):
        try:
            with open(STATE,encoding="utf-8") as f: state=json.load(f)
        except Exception: pass
    all_channels=[]
    for source in reg.get("sources",[]):
        if source.get("enabled") and source.get("public"):
            body=fetch(source.get("playlist",""))
            if body: all_channels.extend(parse_m3u(source["id"], source["id"], source["name"])) if False else all_channels.extend(parse_m3u(body, source["id"], source["name"]))
    # Stable de-duplication and bounded rolling scan.
    unique=list({c["id"]:c for c in all_channels}.values())
    if not unique:
        print(json.dumps(state,indent=2)); return
    cursor=int(state.get("cursor",0)) % len(unique)
    batch=[unique[(cursor+i)%len(unique)] for i in range(min(BATCH_SIZE,len(unique)))]
    for c in batch:
        result=health(c["url"])
        c.pop("url",None)
        c["checkedAt"]=int(time.time())
        state.setdefault("channels",{})[c["id"]]={**c,**result}
    state["cursor"]=(cursor+len(batch)) % len(unique)
    state["updatedAt"]=int(time.time())
    state["totalKnownChannels"]=len(unique)
    state["lastBatchSize"]=len(batch)
    with open(STATE,"w",encoding="utf-8") as f: json.dump(state,f,separators=(",",":"))
    print(json.dumps({"checked":len(batch),"totalKnownChannels":len(unique),"cursor":state["cursor"]},indent=2))

if __name__ == "__main__": main()
