#!/usr/bin/env python3
"""Probe the QA source fixture from either the runner host or Android emulator.
The caller supplies QA_SOURCE_BASE so host-side checks use loopback while
emulator-side checks can use Android's 10.0.2.2 host alias."""
import json
import os
import urllib.parse
import urllib.request

BASE = os.environ.get("QA_SOURCE_BASE", "http://10.0.2.2:8765")

def get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return r.read().decode()

health = json.loads(get("/health"))
assert health.get("ok") is True

qs = urllib.parse.urlencode({"username":"qauser","password":"qapass"})
info = json.loads(get("/player_api.php?" + qs))
assert info["user_info"]["auth"] == 1

streams = json.loads(get("/player_api.php?" + qs + "&action=get_live_streams"))
assert len(streams) >= 2
assert any(x.get("name") == "QA Sports One" for x in streams)

m3u = get("/playlist.m3u")
assert m3u.startswith("#EXTM3U")
assert "QA Sports One" in m3u and "QA Sports Two" in m3u

print(f"QA source probe passed: Xtream auth/catalog + M3U playlist ({BASE})")
