# Season-Aware Schedule Intelligence

XSportsX now treats a missing schedule as a decision problem instead of assuming the provider failed.

## Decision loop

`NO SCHEDULE -> CHECK SEASON -> OFF SEASON OR SEARCH -> DISCOVER -> VALIDATE -> MERGE -> LEARN`

### Off season

If the league is outside its configured season window and there is no recent/upcoming evidence, the refresh records the gap as inactive and avoids expensive Google/web discovery on every run. The existing inactive cadence is used for rechecks.

### In season

If the league is active, the system immediately escalates after the normal provider matrix/cache path has failed. Discovery searches year-aware variants for official schedules, fixtures, schedule APIs/JSON, and results. Search results are fetched and checked for structured sports event data before they can contribute events.

### Unknown

Unknown leagues are configured to remain actionable by default rather than silently suppressing a schedule that may exist.

## Evidence and promotion

Known official sources and authoritative providers remain preferred. A discovered source must return parseable event data, pass validation, survive repeated observations, and meet the confidence threshold before promotion. Canonical event identity/dedup remains the final merge gate.

User-authorized Xtream remains Tier 0 for the user's actual channel/source resolution; credentials are never written to discovery or AI memory.

## Feed telemetry

The canonical feed records `seasonIntelligence` and `scheduleGapResolution`, including active gaps, off-season gaps, searched active gaps, and unresolved gaps. This lets the Sports Brain/Agent distinguish “no games because the league is off” from “we still need to find the schedule.”
