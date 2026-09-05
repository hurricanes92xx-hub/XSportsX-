package com.xsportsx.app

import java.time.Instant
import java.time.temporal.ChronoUnit

/**
 * UFC schedule providers commonly expose the fight night as one event even though
 * UFC publishes separate broadcast sessions. Keep those sessions as separate app
 * events so the schedule and stream resolver can target the correct card.
 *
 * These offsets are copied from UFC's published TV schedule for the currently
 * announced cards; no session is invented when it is not in the known schedule.
 */
object UfcSessionExpander {
    private data class Spec(val key: String, val label: String, val hoursBeforeMain: Long)

    private val specs = listOf(
        Spec("hooker parnasse", "Prelims", 3),
        Spec("silva delgado", "Early Prelims", 4),
        Spec("silva delgado", "Prelims", 2),
        Spec("van pantoja", "Early Prelims", 4),
        Spec("van pantoja", "Prelims", 2),
        Spec("rosas jr barcelos", "Prelims", 2),
        Spec("rosas jr barcelos", "Early Prelims", 1)
    )

    fun expand(events: List<SportsEvent>): List<SportsEvent> {
        if (events.isEmpty()) return events
        val result = ArrayList<SportsEvent>(events.size + 8)
        result += events

        events.filter { it.league.equals("UFC", true) }.forEach { main ->
            val normalized = normalize(main.title)
            if (normalized.isBlank()) return@forEach
            val matched = specs.filter { normalized.contains(it.key) }
            matched.forEach { spec ->
                if (events.any { sameSession(it, main, spec.label) } || result.any { sameSession(it, main, spec.label) }) return@forEach
                val start = runCatching { Instant.parse(main.startUtc).minus(spec.hoursBeforeMain, ChronoUnit.HOURS).toString() }.getOrNull() ?: return@forEach
                result += main.copy(
                    id = "${EventIdentity.id(main)}:${normalize(spec.label).replace(' ', '-')}",
                    title = "${main.title} — ${spec.label}",
                    startUtc = start,
                    home = "",
                    away = "",
                    homeLogo = "",
                    awayLogo = "",
                    broadcast = main.broadcast.ifBlank { "Paramount+" }
                )
            }
        }
        return result
    }

    private fun sameSession(event: SportsEvent, main: SportsEvent, label: String): Boolean {
        if (!event.league.equals("UFC", true)) return false
        if (!event.title.contains(label, true)) return false
        return normalize(event.title).contains(normalize(main.title)) ||
            normalize(main.title).contains(normalize(event.title.substringBefore(" — ")))
    }

    private fun normalize(value: String): String = value.lowercase()
        .replace('’', '\'')
        .replace(Regex("[^a-z0-9]+"), " ")
        .trim()
        .replace(Regex("\\s+"), " ")
}
