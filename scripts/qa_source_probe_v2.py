#!/usr/bin/env python3
"""Probe the local QA source fixture from the GitHub runner."""
import json, urllib.parse, urllib.request
BASE = "http://127.0.0.1:8765"
def get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return r.read().decode()
assert json.loads(get("/health"))["ok"] is True
qs = urllib.parse.urlencode({"username":"qauser","password":"qapass"})
info = json.loads(get("/player_api.php?" + qs))
assert info["user_info"]["auth"] == 1
streams = json.loads(get("/player_api.php?" + qs + "&action=get_live_streams"))
assert len(streams) >= 2 and any(x.get("name") == "QA Sports One" for x in streams)
m3u = get("/playlist.m3u")
assert m3u.startswith("#EXTM3U") and "QA Sports One" in m3u and "QA Sports Two" in m3u
print("QA source probe passed: Xtream auth/catalog + M3U playlist")
