# XSportsX / USportz

XSportsX is now rebuilt around the USportz sports core: fast Nuvio-compatible live sports catalogs, cached public scoreboard metadata, authorized Xtream IPTV indexing, and event-to-channel matching.

## Render

The Render service remains named `xsportsx`, uses the existing Node web-service model, auto-deploys from `main`, and health-checks `/health`. Xtream credentials remain Render environment secrets and are never committed here.

Required Render environment variables:

- `XTREAM_BASE_URL`
- `XTREAM_USERNAME`
- `XTREAM_PASSWORD`

Optional tuning:

- `CACHE_TTL_SECONDS` (default `300`)
- `SCOREBOARD_TTL_SECONDS` (default `60`)
- `REQUEST_TIMEOUT_MS` (default `7000`)

## Endpoints

- `/manifest.json`
- `/catalog/channel/{league}.json`
- `/meta/channel/{id}.json`
- `/stream/channel/{id}.json`
- `/health`
- `/api/xtream/status`
- `/api/cache/refresh`

The old XSportsX repair/workflow stack is intentionally removed so the project can be rebuilt cleanly from the USportz core.
