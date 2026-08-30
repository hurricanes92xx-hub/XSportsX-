# XSportsX Sports Source

The schedule system is now an external service rather than an Android provider stack.

## Runtime flow

```text
ESPN / NCAA / special providers
          |
          v
  XSportsX Sports Source
  - provider selection
  - normalization
  - UTC timestamps
  - caching
  - provider health
  - Xtream event matching
          |
          +---- /api/schedule ----> Android Mobile
          |
          +---- /api/schedule ----> Android TV
```

## API

- `GET /api/leagues`
- `GET /api/schedule?days=3`
- `GET /api/schedule?league=WNBA&days=3`
- `GET /api/live`
- `GET /api/event/:id`
- `GET /api/event/:id/streams`
- `GET /api/status`
- `GET /health`

## Provider ownership

ESPN handles major leagues and the broad college football/basketball feeds. NCAA's scoreboard API handles NCAA sports where NCAA-specific coverage is the stronger source, including women's volleyball and men's/women's soccer.

The Android apps do not contain provider URLs, provider fallback chains, GitHub schedule downloads, or NCAA request fan-out anymore. They only consume the normalized source API.

The Render service is named `xsportsx-sports-source` and uses the repository root `sports-source.js` as its only runtime entry point.
