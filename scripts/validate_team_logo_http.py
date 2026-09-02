#!/usr/bin/env python3
"""Validate that every referenced team-logo URL is reachable over HTTP(S).

This complements the coverage audit: a populated logo field is not enough if
its remote asset returns 404/403 or another unusable response.
"""
from __future__ import annotations

import json
import sys
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


def urls_from_payload() -> set[str]:
    urls: set[str] = set()
    if CACHE.exists():
        payload = json.loads(CACHE.read_text(encoding="utf-8"))
        for value in (payload.get("teams") or {}).values():
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                urls.add(value.strip())
    feed = json.loads(FEED.read_text(encoding="utf-8"))
    for event in feed.get("events") or []:
        for field in ("awayLogo", "homeLogo", "logo", "leagueLogo"):
            value = event.get(field)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                urls.add(value.strip())
    return urls


def check(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "XSportsX-LogoValidator/1.0", "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/png,image/*,*/*;q=0.8"})
    try:
        with urlopen(req, timeout=TIMEOUT) as response:
            status = int(response.status)
            content_type = response.headers.get("Content-Type", "")
            body = response.read(64)
            return {"url": url, "ok": 200 <= status < 400, "status": status, "content_type": content_type, "bytes_sampled": len(body), "error": None}
    except HTTPError as exc:
        return {"url": url, "ok": False, "status": int(exc.code), "content_type": exc.headers.get("Content-Type", "") if exc.headers else "", "bytes_sampled": 0, "error": str(exc)}
    except (URLError, TimeoutError, OSError) as exc:
        return {"url": url, "ok": False, "status": None, "content_type": "", "bytes_sampled": 0, "error": str(exc)}
    except Exception as exc:
        return {"url": url, "ok": False, "status": None, "content_type": "", "bytes_sampled": 0, "error": f"{type(exc).__name__}: {exc}"}


def main() -> None:
    urls = sorted(urls_from_payload())
    print(f"Validating {len(urls)} unique team-logo URLs with {WORKERS} workers")
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(check, url): url for url in urls}
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda row: row["url"])
    failures = [row for row in results if not row["ok"]]
    report = {
        "schema_version": 1,
        "urls_checked": len(results),
        "urls_ok": len(results) - len(failures),
        "urls_failed": len(failures),
        "failures": failures,
        "rule": "Every referenced team-logo URL must return an HTTP 2xx/3xx response with at least one readable byte.",
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"urls_checked": len(results), "urls_ok": report["urls_ok"], "urls_failed": report["urls_failed"]}, indent=2))
    if failures:
        for row in failures[:50]:
            print(f"FAIL {row['status']} {row['url']} :: {row['error']}")
        raise SystemExit(f"TEAM LOGO HTTP VALIDATION FAILED: {len(failures)} of {len(results)} URLs failed")


if __name__ == "__main__":
    main()
