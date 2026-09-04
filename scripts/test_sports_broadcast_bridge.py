#!/usr/bin/env python3
import sports_broadcast_bridge as b

info=b.build_event_intelligence({"id":"test","league":"NFL","title":"Synthetic Test Match","startUtc":"2026-09-04T19:00:00Z"})
assert info.get("schema")==1
assert isinstance(info.get("liveCandidates"),list)
assert isinstance(info.get("scheduleCandidates"),list)
for row in info.get("liveCandidates") or []:
    assert row.get("authority") in {"official","espn","discovered"}
    assert row.get("verifiedForPlayback") is False
print("SPORTS_BROADCAST_BRIDGE: PASS")
