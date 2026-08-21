# XSportsX

**XSportsX** is a production-oriented live-sports addon for Nuvio/Stremio.

Nuvio addons use the standard Stremio addon protocol (`catalog`, `meta`, and `stream`) and run their server-side source logic remotely. XSportsX follows that architecture.

## What is included

### Sports coverage

- NFL
- NBA
- NHL
- MLB
- NCAA football
- NCAA basketball
- MLS
- Premier League
- UFC
- Formula 1
- MotoGP

### Home-screen catalogs

- 🔴 LIVE NOW
- STARTING SOON
- TODAY
- ⭐ FAVORITES
- league-specific rows

### Source engine

1. Public event metadata discovery.
2. Optional authorized M3U playlist ingestion.
3. Optional authorized Xtream-compatible ingestion.
4. Optional authorized direct event streams.
5. Optional authorized JSON event feeds.
6. Optional operator-supplied Base64 source URL.
7. Fuzzy team/league matching.
8. Stream scoring.
9. Quality/priority ranking.
10. Circuit breakers for failing providers.
11. TTL caching to reduce provider load.
12. Official watch-page fallback links.

## Important source policy

XSportsX is designed for streams and accounts the operator is authorized to use. It does not discover, guess, brute-force, harvest, or validate leaked IPTV credentials, nor does it include mechanisms intended to bypass provider access controls.

The addon can ingest a playlist URL or Xtream account that you provide and are entitled to access.

## Run

```bash
npm install
cp .env.example .env
npm start
```

Then install:

```text
http://YOUR_HOST:7000/manifest.json
```

For public deployment, use HTTPS.

## Authorized M3U

```env
AUTHORIZED_M3U_SOURCES=[{"name":"My IPTV","url":"https://provider.example/playlist.m3u","priority":100,"minScore":35}]
```

## Authorized Xtream

```env
AUTHORIZED_XTREAM_SOURCES=[{"name":"My Provider","baseUrl":"https://provider.example","username":"USER","password":"PASS","priority":100}]
```

## Direct event source

```env
AUTHORIZED_EVENT_STREAMS=[{"name":"My Feed","eventId":"401234567","url":"https://example.com/live/event.m3u8","priority":200}]
```

## Official links

```env
OFFICIAL_WATCH_LINKS={"ESPN":"https://www.espn.com/watch/","NFL":"https://www.nfl.com/watch/"}
```

## Easy Base64 source URL

When configuring the XSportsX addon, there is now an optional field:

```text
Base64 Source URL (optional)
```

Paste **one public/authorized HTTP(S) URL** into that field. XSportsX will use that URL as an additional source input when its normal event matching needs more sources. It fetches the page/feed, finds Base64 or direct HTTP(S) links, decodes Base64, health-checks discovered media links, and ranks the healthy results.

You do not need to edit JavaScript or hard-code the URL.

For a deployment-wide source instead of per-addon configuration, Render can also use:

```env
BASE64_SOURCE_URLS=https://example.com/my-source
```

Multiple URLs may be separated by commas or new lines. `XSPORTSX_SOURCE_URL` is also accepted as a single-URL alias.

## Base64 Decoder + Link Health Tool

XSportsX includes an attachable utility at:

```text
GET /tools/base64
POST /tools/base64/scan
```

The tool can:

- Accept a site URL and scan its HTML/JavaScript/text for Base64 payloads.
- Accept pasted Base64, HTML, JavaScript, JSON, or M3U text.
- Decode standard and URL-safe Base64.
- Detect nested Base64 up to three layers.
- Extract HTTP(S) URLs from decoded content.
- Health-check discovered links with latency and HTTP status.
- Block localhost, private/reserved IPs, link-local addresses, multicast, and URLs containing embedded credentials.
- Revalidate redirects before allowing a health check.
- Apply payload, page, link-count, and timeout limits to keep the tool fast and bounded.

Example API request:

```json
{
  "site": "https://example.com/page",
  "base64": "",
  "health": true
}
```

The scanner is intended for sources you are authorized to inspect. It does not attempt to bypass authentication, anti-bot controls, or protected provider access.

## Health

```text
GET /health
```

## Tests

```bash
npm test
npm run check
```

## Production architecture

For a larger deployment, put XSportsX behind a reverse proxy and use a persistent cache such as Redis. The provider layer is deliberately separated from the Nuvio HTTP layer so new, permitted sports data/stream providers can be added without rewriting the addon.

## Upcoming matches

XSportsX now loads up to **7 days of schedules** and exposes:

- `TODAY`
- `STARTING SOON` — next 2 hours
- `UPCOMING — NEXT 7 DAYS`
- league-specific upcoming rows

The addon refreshes the schedule cache automatically, so games added or rescheduled by the metadata provider can appear without rebuilding the addon.

## About SportsZX sources

XSportsX does not copy private SportsZX endpoints, extract proprietary provider credentials, or reverse-engineer/bypass access controls.

If you have a provider you are authorized to use, add it to the supported source configuration. The provider abstraction is intentionally designed so additional permitted sources can be plugged in without changing the Nuvio API layer.

## v2.2 feature set

XSportsX benchmarks the public feature set of current Nuvio sports addons: broad sport coverage, multi-day fixtures, timezone-aware configuration, favorite-team planning, multi-source aggregation, caching, provider isolation, and source ranking.

The XSportsX implementation intentionally does **not** copy private endpoints, credentials, anti-bot workarounds, or access-control bypass logic from another addon/provider. The provider engine is ready for sources you are authorized to use.

### Why we don't proxy protected streams

XSportsX avoids reproducing provider-specific access-control bypass mechanisms. It returns playable URLs supplied by authorized providers or official watch links instead.

### Configuration

Open:

```text
http://YOUR_HOST:7000/configure
```

The configuration UI lets you select sports, choose a timezone, record favorite teams, and now enter the optional Base64 Source URL. Provider credentials remain server-side.

## Private provider configuration

Private provider credentials belong in Render Environment Variables or a local `.env` file and are not hard-coded into the application source. Private endpoint lists should likewise be supplied through deployment configuration.

Do not publish the `.env` file or share the credentials. Rotate the provider password if the credentials have been exposed elsewhere.

Before deploying, verify that the IPTV account and streams are authorized for your use.

## v2.3 collection-first Nuvio home

The Nuvio home presentation is collection-first instead of exposing every league as a separate event row.

- Added a `🏆 SPORTS LEAGUES` home row with animated GIF league cards.
- League cards open a collection meta containing that league's scheduled events.
- Kept `🔴 LIVE NOW` and `STARTING SOON` as focused event rows.
- Added animated league badge GIFs under `public/leagues/` for NFL, NBA, NHL, MLB, NCAA, WNBA, MLS, Premier League, La Liga, F1, MotoGP, UFC, Boxing, ATP, WTA, PGA, Rugby, Cricket, Darts, and AFL.

## Favorite Teams collection

The Nuvio home catalog includes `⭐ FAVORITE TEAMS` with these team collections:
- Miami Hurricanes Football
- Miami Hurricanes Basketball
- Miami Dolphins
- Miami Heat
- Tampa Bay Lightning

Each team card uses an animated GIF badge and opens a team-specific event collection filtered to the correct league/sport.
