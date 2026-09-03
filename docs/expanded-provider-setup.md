# Expanded Provider Layer

The canonical schedule engine now supports optional independent providers:

- Sportradar — broad major-league and international coverage
- SportsDataIO — major US sports, NCAA, NASCAR, golf, soccer, MMA and F1
- Sportmonks — football/soccer, cricket and Formula 1
- College Football Data API — NCAA football
- MLB Stats API — direct MLB schedule/game state
- NHL API — direct NHL schedule/game state
- PandaScore — esports (endpoint-configured)

## Activation

Paid/provider credentials are read only from environment variables and are never persisted.

GitHub Actions secrets:

- `SPORTRADAR_API_KEY`
- `SPORTSDATAIO_API_KEY`
- `SPORTMONKS_API_TOKEN`
- `CFBD_API_KEY`
- `PANDASCORE_API_TOKEN`

GitHub Actions variables for providers whose endpoint differs by product/league:

- `SPORTRADAR_ENDPOINT_TEMPLATE`
- `SPORTSDATAIO_ENDPOINT_TEMPLATE`
- `SPORTMONKS_ENDPOINT_TEMPLATE`
- `PANDASCORE_ENDPOINT_TEMPLATE`

Templates may use `{league}` (URL-encoded) or `{league_raw}`. This keeps credentials out of source control and lets the same adapter support different subscribed API products.

## Failover behavior

Each league is assigned a primary, secondary, tertiary and cached recovery path. Providers without credentials/configuration are kept as `standbyProviders` rather than being called and generating false failures. Successful providers are health-scored using success rate, returned event count, latency and consecutive failures; the healthiest configured provider is promoted automatically.

MLB and NHL use direct league APIs without requiring a paid credential. Sportradar/SportsDataIO/Sportmonks/CFBD/PandaScore become active automatically when their required Actions configuration is present.
