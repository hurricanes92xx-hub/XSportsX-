#!/usr/bin/env python3
"""Validate team-logo URLs actually referenced by the canonical schedule feed.

The persistent team-logo catalog intentionally contains historical and broader
sport/team entries that are not necessarily used by the current feed. Those
cache-only URLs must not block publication. We validate every logo URL that is
actually referenced by a current event, while separately reporting stale
cache-only URLs for cleanup.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data" / "schedule_feed.json"
CACHE = ROOT / "data" / "team_logo_map.json"
OUT = ROOT / "data" / "team_logo_http_validation.json"
TIMEOUT = 15
WORKERS = 24
LOGO_FIELDS = ("awayLogo", "homeLogo", "logo", "leagueLogo")


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
    req = Request(
        url,
        headers={
            "User-Agent": "XSportsX-LogoValidator/2.0",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/png,image/*,*/*;q=0.8",
        },
    )
    try:
        with urlopen(req, timeout=TIMEOUT) as response:
            status = int(response.status)
            content_type = response.headers.get("Content-Type", "")
            body = response.read(64)
            return {
                "url": url,
                "ok": 200 <= status < 400 and bool(body),
                "status": status,
                "content_type": content_type,
                "bytes_sampled": len(body),
                "error": None,
            }
    except HTTPError as exc:
        return {
            "url": url,
            "ok": False,
            "status": int(exc.code),
            "content_type": exc.headers.get("Content-Type", "") if exc.headers else "",
            "bytes_sampled": 0,
            "error": str(exc),
        }
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
    feed_urls = urls_from_feed()
    cache_urls = urls_from_cache()
    cache_only_urls = cache_urls - feed_urls

    print(f"Validating {len(feed_urls)} current-feed logo URLs with {WORKERS} workers")
    feed_results = validate(feed_urls)
    failures = [row for row in feed_results if not row["ok"]]

    report = {
        "schema_version": 2,
        "feed_urls_checked": len(feed_results),
        "feed_urls_ok": len(feed_results) - len(failures),
        "feed_urls_failed": len(failures),
        "cache_urls_checked": len(cache_urls),
        "cache_only_urls": len(cache_only_urls),
        "cache_only_urls_not_validated": True,
        "failures": failures,
        "rule": "Every team-logo URL actually referenced by a current schedule-feed event must return an HTTP 2xx/3xx response with at least one readable byte. Cache-only historical URLs are reported but do not block publication.",
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "feed_urls_checked": report["feed_urls_checked"],
        "feed_urls_ok": report["feed_urls_ok"],
        "feed_urls_failed": report["feed_urls_failed"],
        "cache_urls_checked": report["cache_urls_checked"],
        "cache_only_urls": report["cache_only_urls"],
    }, indent=2))

    if failures:
        for row in failures[:50]:
            print(f"FAIL {row['status']} {row['url']} :: {row['error']}")
        raise SystemExit(f"TEAM LOGO HTTP VALIDATION FAILED: {len(failures)} current-feed URLs failed")


if __name__ == "__main__":
    main()
