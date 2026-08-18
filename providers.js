import * as coreProviders from "./providers-core.js";
import { freeOfficialLinksForEvent, freeSourceStatus } from "./free-sources.js";

export const getEvents = coreProviders.getEvents;
export const parseM3U = coreProviders.parseM3U;
export const newsStreamsForChannel = coreProviders.newsStreamsForChannel;

export async function streamsFor(event) {
  const key = `free-wrapper:${event.eventId}`;
  const [iptvStreams, freeLinks] = await Promise.all([
    coreProviders.streamsFor(event),
    freeOfficialLinksForEvent(event)
  ]);
  const seen = new Set();
  const combined = [];
  for (const item of [...iptvStreams, ...freeLinks]) {
    const identity = item.url || item.externalUrl || `${item.name}:${item.description}`;
    if (seen.has(identity)) continue;
    seen.add(identity);
    combined.push(item);
  }
  return combined;
}

export function providerStatus() {
  return {
    ...coreProviders.providerStatus(),
    freeOfficialSources: freeSourceStatus()
  };
}
