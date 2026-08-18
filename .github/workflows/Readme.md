# This is a basic workflow to helpXSportsX
XSportsX is a production-oriented live-sports addon for Nuvio/Stremio.
Nuvio addons use the standard Stremio addon protocol (catalog, meta, and stream) and run their server-side source logic remotely. XSportsX follows that architecture.
What is included
Sports coverage
NFL
NBA
NHL
MLB
NCAA football
NCAA basketball
MLS
Premier League
UFC
Formula 1
MotoGP
Home-screen catalogs
🔴 LIVE NOW
STARTING SOON
TODAY
⭐ FAVORITES
league-specific rows
Source engine
Public event metadata discovery.
Optional authorized M3U playlist ingestion.
Optional authorized Xtream-compatible ingestion.
Optional authorized direct event streams.
Optional authorized JSON event feeds.
Fuzzy team/league matching.
Stream scoring.
Quality/priority ranking.
Circuit breakers for failing providers.
TTL caching to reduce provider load.
Official watch-page fallback links.
Important source policy
XSportsX is designed for streams and accounts the operator is authorized to use. It does not discover, guess, brute-force, harvest, or validate leaked IPTV credentials, nor does it include mechanisms intended to bypass provider access controls.
The addon can ingest a playlist URL or Xtream account that you provide and are entitled to access.
Run
npm install
cp .env.example .env
npm start
Then install:
http://YOUR_HOST:7000/manifest.json
For public deployment, use HTTPS.
Authorized M3U
AUTHORIZED_M3U_SOURCES=[{"name":"My IPTV","url":"https://provider.example/playlist.m3u","priority":100,"minScore":35}]
Authorized Xtream
AUTHORIZED_XTREAM_SOURCES=[{"name":"My Provider","baseUrl":"https://provider.example","username":"USER","password":"PASS","priority":100}]
Direct event source
AUTHORIZED_EVENT_STREAMS=[{"name":"My Feed","eventId":"401234567","url":"https://example.com/live/event.m3u8","priority":200}]
Official links
OFFICIAL_WATCH_LINKS={"ESPN":"https://www.espn.com/watch/","NFL":"https://www.nfl.com/watch/"}
Health
GET /health
Tests
npm test
npm run check
Production architecture
For a larger deployment, put XSportsX behind a reverse proxy and use a persistent cache such as Redis. The provider layer is deliberately separated from the Nuvio HTTP layer so new, permitted sports data/stream providers can be added without rewriting the addon.
Upcoming matches
XSportsX now loads up to 7 days of schedules and exposes:
TODAY
STARTING SOON — next 2 hours
UPCOMING — NEXT 7 DAYS
league-specific upcoming rows
The addon refreshes the schedule cache automatically, so games added or rescheduled by the metadata provider can appear without rebuilding the addon.
About SportsZX sources
I checked public references for SportsZX. The current public descriptions I could verify describe it primarily as a live-scores/fixtures app and say it does not itself host full-match streams. Public user discussions also mention SportsZX as a standalone sports app, but I could not verify a public, authoritative list of the underlying stream providers it uses. citeturn0search0turn0reddit36
XSportsX therefore does not copy private SportsZX endpoints, extract its proprietary provider credentials, or reverse-engineer/bypass its access controls.
If you have a provider you are authorized to use, add it to AUTHORIZED_M3U_SOURCES, AUTHORIZED_XTREAM_SOURCES, or AUTHORIZED_EVENT_STREAMS. The provider abstraction is intentionally designed so additional permitted sources can be plugged in without changing the Nuvio API layer.
v2.2 feature set
XSportsX now benchmarks the public feature set of current Nuvio sports addons: broad sport coverage, multi-day fixtures, timezone-aware configuration, favorite-team planning, multi-source aggregation, caching, provider isolation, and source ranking. Current community examples advertise broad coverage across NBA/NFL/NHL/MLB/F1/UFC/ATP/WTA/rugby/golf/cricket/darts and more. citeturn1reddit14turn1search0
The XSportsX implementation intentionally does not copy private endpoints, credentials, anti-bot workarounds, or access-control bypass logic from another addon/provider. The provider engine is ready for sources you are authorized to use.
Why we don't proxy protected streams
Some community sports addons describe server-side reverse proxies that add provider-specific Referer/Origin headers or otherwise work around CDN restrictions. citeturn1search1turn1reddit21 XSportsX avoids reproducing those bypass mechanisms. It returns playable URLs supplied by authorized providers or official watch links instead.
Configuration
Open:
http://YOUR_HOST:7000/configure
The configuration UI lets you select sports, choose a timezone, and record favorite teams for the deployment. Provider credentials remain server-side in environment variables.
Private provider configuration
Private provider credentials are stored only in the local .env file and are not hard-coded into the application source. The supplied alternate provider domains are stored in data/private-endpoints.json.
Do not publish the .env file or share the credentials. Rotate the provider password if the credentials have been exposed elsewhere.
Before deploying, verify that the IPTV account and streams are authorized for your use. you get started with Actions

name: CI

# Controls when the workflow will run
on:
  # Triggers the workflow on push or pull request events but only for the "main" branch
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]

  # Allows you to run this workflow manually from the Actions tab
  workflow_dispatch:

# A workflow run is made up of one or more jobs that can run sequentially or in parallel
jobs:
  # This workflow contains a single job called "build"
  build:
    # The type of runner that the job will run on
    runs-on: ubuntu-latest

    # Steps represent a sequence of tasks that will be executed as part of the job
    steps:
      # Checks-out your repository under $GITHUB_WORKSPACE, so your job can access it
      - uses: actions/checkout@v4

      # Runs a single command using the runners shell
      - name: Run a one-line script
        run: echo Hello, world!

      # Runs a set of commands using the runners shell
      - name: Run a multi-line script
        run: |
          echo Add other actions to build,
          echo test, and deploy your project.
