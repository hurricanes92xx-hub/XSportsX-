# XSportsX

**XSportsX is a standalone sports streaming Android app for Mobile and Android TV.**

This project is no longer a Nuvio add-on. It is a full Android sports application with dedicated Mobile and TV experiences, live sports, networks, favorites/My Teams, college teams, schedules, upcoming games, and source login support.

## Downloads

### Android TV

**Downloader code:** `4708771`

**Downloader URL:** https://go.aftvnews.com/4708771

The Downloader code redirects to the current XSportsX TV APK release.

Direct GitHub release download:
https://github.com/hurricanes92xx-hub/XSportsX-/releases/latest/download/XSportsX-TV.apk

### Android Mobile

Direct GitHub release download:
https://github.com/hurricanes92xx-hub/XSportsX-/releases/latest/download/XSportsX-Mobile.apk

## Features

- Live sports and sports networks
- Mobile and Android TV optimized interfaces
- My Teams / Favorites
- NFL, NBA, MLB, NHL, UFC and other sports
- College sports favorites and team coverage
- Team schedules, live games and upcoming games
- Team-specific news surfaces
- Xtream credentials login
- M3U playlist login
- TV QR login and regular/manual login
- Fast source discovery and cached matching
- Automatic APK update checking
- Dedicated QA coverage for Mobile and TV

## Release / Update Architecture

Production APKs are built separately from the QA pipeline. Each production release produces signed Mobile and Android TV APKs and synchronizes `update.json` with the exact release version and current APK URLs.

QA/emulator/source-fixture tests live in the separate **XSportsX QA — Mobile + TV** workflow and do not publish production APKs.

## Project Status

XSportsX is actively developed as a standalone Android sports application. The repository's production branch contains the release APK build pipeline, while the QA workflow provides isolated Mobile/TV regression testing.
