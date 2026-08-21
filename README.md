# XSportsX

**XSportsX** is a production-oriented live-sports addon for Nuvio/Stremio.

## Easy source URL setup

When configuring XSportsX in Nuvio/Stremio, use the optional **Base64 Source URL** field. Paste the public/authorized page, feed, M3U, JSON, or text URL that you want XSportsX to use as an additional source input.

When normal Xtream/event matching needs more sources, XSportsX fetches that URL, finds Base64 or direct HTTP(S) links, decodes Base64, health-checks discovered media links, and adds healthy results to the event source list.

For a deployment-wide source, Render can also set:

```env
BASE64_SOURCE_URLS=https://example.com/my-source
```

Multiple URLs may be separated by commas or new lines. `XSPORTSX_SOURCE_URL` is accepted as a single-URL alias.

The scanner is bounded and does not harvest credentials or bypass authentication/access controls.

## Base64 Decoder + Link Health Tool

XSportsX includes:

```text
GET /tools/base64
POST /tools/base64/scan
```

The browser tool accepts a site URL or pasted Base64/code. It supports URL-safe Base64, nested Base64 up to three layers, URL extraction, HTTP status/latency checks, and SSRF protections for private/reserved hosts and credential-bearing URLs.

## Sports coverage

NFL, NBA, NHL, MLB, NCAA football, NCAA basketball, MLS, Premier League, UFC, Formula 1, and MotoGP, plus the existing XSportsX catalog and favorite-team collections.

## Authorized sources

XSportsX is designed for streams and accounts the operator is authorized to use. Keep private provider credentials in Render Environment Variables or a local `.env` file. Never commit credentials to GitHub.

## Run

```bash
npm install
cp .env.example .env
npm start
```

Install the deployed `/manifest.json` URL in Nuvio/Stremio.

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

The source provider layer remains separated from the Nuvio HTTP layer. Caching, source scoring, provider isolation, and the existing XSportsX event catalogs remain intact while the optional configured Base64 source acts as an additional fallback.
