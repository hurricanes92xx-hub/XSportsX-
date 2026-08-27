# Fast public source selection

The public-source path is intentionally split into two phases.

1. **Background/cold-start discovery**: `PublicSourceResolver` loads the approved public registry, filters sports candidates, validates HTTPS sources, health-checks candidates concurrently, and caches the result.
2. **Event click selection**: `FastPublicSourceSelector` consults `PublicSourceHealthIndex` first. Known-good event/league/network candidates are returned before a cold registry lookup.
3. **Playback verification**: the selected candidate should be verified by the player/source adapter. A failed candidate must be recorded as a failure and the next ranked candidate tried.

The index stores no Xtream credentials or user playlist URLs. Public-source discovery must remain limited to legitimately public/authorized sources and must not bypass authentication, DRM, paywalls, or regional access controls.
