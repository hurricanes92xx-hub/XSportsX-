# Authorized Stalker / MAG sources

XSportsX can resolve live-game channels from Stalker/MAG portals that you are authorized to access.

Configure the deployment environment variable `AUTHORIZED_STALKER_SOURCES` as a JSON array:

```json
[
  {
    "name": "My Stalker",
    "portal": "https://provider.example",
    "mac": "00:1A:79:XX:XX:XX",
    "priority": 100,
    "minScore": 45,
    "maxMatches": 8
  }
]
```

The adapter performs a normal Stalker handshake, retrieves the channel list, matches channel names/groups against the live event teams and league, then asks the portal for a playable channel link when required.

## Source selection

M3U, Xtream-compatible, Stalker, direct authorized event feeds, and official links are aggregated by the existing XSportsX stream resolver. Higher matchup scores and provider priority rank first.

## Failure handling

Stalker providers use a circuit breaker. Repeated provider failures temporarily open the circuit and cached channel data can be used while it recovers. A failed `create_link` response is not returned as a playable stream.

For best results, keep credentials in Render environment variables rather than committing them to GitHub.

## Example Render variable

`AUTHORIZED_STALKER_SOURCES=[{"name":"My Stalker","portal":"https://provider.example","mac":"00:1A:79:XX:XX:XX","priority":100,"minScore":45}]`

Only configure portals, MAC addresses, and streams that you are authorized to use.
