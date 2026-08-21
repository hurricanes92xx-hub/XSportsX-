# XSportsX

**XSportsX** is a production-oriented live-sports addon for Nuvio/Stremio.

Nuvio addons use the standard Stremio addon protocol (`catalog`, `meta`, and `stream`) and run their server-side source logic remotely. XSportsX follows that architecture.

## Easy source URL setup

When installing/configuring XSportsX, use the optional **Base64 Source URL** field. Paste the public/authorized page, feed, M3U, JSON, or text URL that you want XSportsX to use as an additional source input.

XSportsX will fetch that URL only when its normal event matching needs more sources, decode Base64 embedded in the response, extract HTTP(S) media links, health-check them, and add healthy results to the event's source list.

You can also set a deployment-wide URL in Render:

```env
BASE64_SOURCE_URLS=https://example.com/my-source
```

Multiple URLs may be separated by commas or new lines. `XSPORTSX_SOURCE_URL` is accepted as a single-URL alias.

The scanner does not harvest credentials or bypass authentication/access controls.

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

## Run

```bash
npm install
cp .env.example .env
npm start
```

Then install the manifest from your deployed host.

## Authorized sources

Keep private credentials in Render Environment Variables or a local `.env` file. Do not publish credentials in GitHub.

## Base64 Decoder + Link Health Tool

XSportsX includes an attachable utility at:

```text
GET /tools/base64
POST /tools/base64/scan
```

It can accept a site URL or pasted Base64/code, decode standard and URL-safe Base64, inspect up to three nested layers, extract HTTP(S) links, and health-check discovered links. Private/reserved hosts and credential-bearing URLs are blocked.

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

For a larger deployment, put XSportsX behind a reverse proxy and use a persistent cache such as Redis. The provider layer is separated from the Nuvio HTTP layer so permitted sources can be added without rewriting the addon API.

## Favorite Teams

The Nuvio home includes favorite-team collections for Miami Hurricanes Football, Miami Hurricanes Basketball, Miami Dolphins, Miami Heat, and Tampa Bay Lightning.
