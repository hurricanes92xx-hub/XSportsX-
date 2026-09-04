#!/usr/bin/env python3
from datetime import datetime, timezone
from season_intelligence import analyze


def main():
    now = datetime(2026, 9, 4, tzinfo=timezone.utc)
    nfl = analyze("NFL", [], now)
    mlb = analyze("MLB", [], now)
    winter = analyze("NCAA BB", [], now)
    assert nfl["active"] is True, nfl
    assert mlb["active"] is True, mlb
    assert winter["active"] is False, winter
    # A real observed event keeps a league active even if its configured window
    # is stale or the calendar policy has not caught a special competition.
    observed = [{"league":"NCAA BB", "startUtc":"2026-12-01T00:00:00Z"}]
    assert analyze("NCAA BB", observed, now)["active"] is True
    print("season intelligence: PASS")


if __name__ == "__main__":
    main()
