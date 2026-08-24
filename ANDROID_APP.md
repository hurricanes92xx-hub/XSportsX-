# XSportsX Native Android App

The `android-app` branch contains the new standalone XSportsX Android client.

## UI direction
- Obsidian black sports-command-center aesthetic
- Red/orange XSportsX accent system
- Live / Search / Sources / Settings rail
- Featured event hero
- League filters
- UFC, Road to UFC, Dana White's Contender Series and Boxing sections
- Event detail sheet with source matching entry point
- Phone, tablet and Android TV friendly layouts

## Data architecture
The app UI is intentionally separated from stream discovery. The next integration layer will connect the existing XSportsX event engine to the app and perform matching against the user's authorized Xtream/M3U source.

The app does not bundle or redistribute third-party streams. It only plays sources the user is authorized to access.

## Build
GitHub Actions builds a debug APK from `.github/workflows/android.yml`.
