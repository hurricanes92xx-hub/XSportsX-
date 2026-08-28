#!/usr/bin/env python3
"""Local-only deterministic Xtream/M3U fixture server for emulator QA.
Never contacts or stores real provider credentials."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HOST = os.environ.get("QA_SOURCE_HOST", "0.0.0.0")
PORT = int(os.environ.get("QA_SOURCE_PORT", "8765"))
USER = "qauser"
PASS = "qapass"
TOKEN = "qa-token"

CHANNELS = [
    {"num": "101", "name": "QA Sports One", "stream_type": "live", "stream_id": "101", "stream_icon": "", "epg_channel_id": "qa.one", "category_id": "1"},
    {"num": "102", "name": "QA Sports Two", "stream_type": "live", "stream_id": "102", "stream_icon": "", "epg_channel_id": "qa.two", "category_id": "1"},
]

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send_json(self, payload, code=200):
        raw = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/health":
            self.send_json({"ok": True, "fixture": "xsportsx-qa"})
            return
        if u.path == "/playlist.m3u":
            body = "#EXTM3U\n" + "\n".join(
                f'#EXTINF:-1 tvg-id="{c["epg_channel_id"]}" group-title="QA Sports",{c["name"]}\nhttp://10.0.2.2:{PORT}/stream/{c["stream_id"]}'
                for c in CHANNELS
            ) + "\n"
            raw = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", "audio/x-mpegurl")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers(); self.wfile.write(raw); return
        if u.path == "/player_api.php":
            if q.get("username", [""])[0] != USER or q.get("password", [""])[0] != PASS:
                self.send_json({"user_info": {"auth": 0, "status": "Disabled"}}); return
            action = q.get("action", [""])[0]
            if not action:
                self.send_json({"user_info": {"auth": 1, "status": "Active", "username": USER, "password": PASS, "exp_date": "4102444800", "message": TOKEN}, "server_info": {"url": "10.0.2.2", "port": str(PORT), "https_port": str(PORT)}}); return
            if action == "get_live_categories":
                self.send_json([{"category_id":"1","category_name":"QA Sports","parent_id":0}]); return
            if action == "get_live_streams":
                self.send_json(CHANNELS); return
            if action == "get_short_epg":
                self.send_json({"epg_listings": []}); return
            self.send_json([]); return
        if u.path.startswith("/stream/"):
            self.send_response(200); self.send_header("Content-Type", "video/mp2t"); self.end_headers(); return
        self.send_response(404); self.end_headers()

class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True

if __name__ == "__main__":
    print(f"QA source fixture listening on {HOST}:{PORT}", flush=True)
    ReusableThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
