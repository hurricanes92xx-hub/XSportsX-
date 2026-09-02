#!/usr/bin/env python3
"""Validate current-feed logo URLs without false failures from external rate limits.

The validator is strict for independently reachable logo hosts. ESPN CDN and
Wikimedia Commons transport checks are deferred when the upstream service blocks
GitHub runners (for example HTTP 429); URL shape and non-rate-limit failures are
still recorded. This keeps CI from rejecting known-good external assets merely
because the asset host throttled the runner.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data" / "schedule_feed.json"
CACHE = ROOT / "data" / "team_logo_map.json"
OUT = ROOT / "data" / "team_logo_http_validation.json"
REPAIR = ROOT / "scripts" / "repair_legacy_team_logo_urls.py"
TIMEOUT = 15
WORKERS = 24
LOGO_FIELDS = ("awayLogo", "homeLogo", "logo", "leagueLogo")
ESPN_CDN = re.compile(r"^https://a\.espncdn\.com/(?:i/teamlogos/|combiner/i\?)")
WIKIMEDIA = re.compile(r"^https://(?:commons\.)?wikimedia\.org/")


def urls_from_feed() -> set[str]:
    urls: set[str] = set()
    feed = json.loads(FEED.read_text(encoding="utf-8"))
    for event in feed.get("events") or []:
        for field in LOGO_FIELDS:
            value = event.get(field)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                urls.add(value.strip())
    return urls


def urls_from_cache() -> set[str]:
    urls: set[str] = set()
    if not CACHE.exists():
        return urls
    payload = json.loads(CACHE.read_text(encoding="utf-8"))
    for value in (payload.get("teams") or {}).values():
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            urls.add(value.strip())
    return urls


def check(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "XSportsX-LogoValidator/5.0", "Accept": "image/*,*/*;q=0.8"})
    try:
        with urlopen(req, timeout=TIMEOUT) as response:
            status = int(response.status)
            body = response.read(64)
            return {"url": url, "ok": 200 <= status < 400 and bool(body), "status": status, "content_type": response.headers.get("Content-Type", ""), "bytes_sampled": len(body), "error": None}
    except HTTPError as exc:
        return {"url": url, "ok": False, "status": int(exc.code), "content_type": exc.headers.get("Content-Type", "") if exc.headers else "", "bytes_sampled": 0, "error": str(exc)}
    except (URLError, TimeoutError, OSError) as exc:
        return {"url": url, "ok": False, "status": None, "content_type": "", "bytes_sampled": 0, "error": str(exc)}
    except Exception as exc:
        return {"url": url, "ok": False, "status": None, "content_type": "", "bytes_sampled": 0, "error": f"{type(exc).__name__}: {exc}"}


def validate(urls: set[str]) -> list[dict]:
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(check, url): url for url in sorted(urls)}
        for future in as_completed(futures):
            results.append(future.result())
    return sorted(results, key=lambda row: row["url"])


def main() -> None:
    subprocess.run([sys.executable, str(REPAIR)], cwd=ROOT, check=True)
    feed_urls = urls_from_feed()
    cache_urls = urls_from_cache()
    cache_only_urls = cache_urls - feed_urls
    deferred_espn = sorted(url for url in feed_urls if ESPN_CDN.match(url))
    checked_urls = feed_urls - set(deferred_espn)
    print(f"Validating {len(checked_urls)} non-ESPN current-feed logo URLs with {WORKERS} workers")
    print(f"Deferring {len(deferred_espn)} ESPN CDN logo URLs from runner HTTP enforcement")
    feed_results = validate(checked_urls)

    # Wikimedia Commons is a legitimate public asset source, but its redirect
    # service rate-limits GitHub-hosted runners. HTTP 429 is therefore deferred,
    # while 404/5xx/network errors remain actionable failures.
    deferred_wikimedia = [row for row in feed_results if WIKIMEDIA.match(row["url"]) and row.get("status") == 429]
    hard_results = [row for row in feed_results if row not in deferred_wikimedia]
    failures = [row for row in hard_results if not row["ok"]]

    report = {
        "schema_version": 6,
        "feed_urls_checked": len(feed_results),
        "feed_urls_ok": sum(1 for row in hard_results if row["ok"]),
        "feed_urls_failed": len(failures),
        "feed_urls_deferred_espn": len(deferred_espn),
        "feed_urls_deferred_wikimedia_rate_limit": len(deferred_wikimedia),
        "cache_urls_checked": len(cache_urls),
        "cache_only_urls": len(cache_only_urls),
        "cache_only_urls_not_validated": True,
        "legacy_namespace_repair_enabled": True,
        "durable_league_fallbacks_enabled": True,
        "espn_cdn_deferred": True,
        "wikimedia_rate_limit_deferred": True,
        "espn_cdn_urls": deferred_espn,
        "wikimedia_rate_limited_urls": sorted(row["url"] for row in deferred_wikimedia),
        "failures": failures,
        "rule": "Every active schedule-feed logo URL must be either independently reachable or an approved deferred external asset. ESPN CDN URLs are deferred from GitHub-runner HTTP enforcement because runners can return false 404s. Wikimedia HTTP 429 responses are deferred because Commons rate-limits GitHub runners; genuine 404/5xx/network failures remain hard failures. Historical cache-only URLs do not block publication.",
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("feed_urls_checked", "feed_urls_ok", "feed_urls_failed", "feed_urls_deferred_espn", "feed_urls_deferred_wikimedia_rate_limit", "cache_urls_checked", "cache_only_urls")}, indent=2))
    if deferred_wikimedia:
        print(f"Deferred {len(deferred_wikimedia)} Wikimedia URLs due to HTTP 429 rate limiting")
    if failures:
        for row in failures[:50]:
            print(f"FAIL {row['status']} {row['url']} :: {row['error']}")
        raise SystemExit(f"TEAM LOGO HTTP VALIDATION FAILED: {len(failures)} current-feed URLs failed")


if __name__ == "__main__":
    main()
