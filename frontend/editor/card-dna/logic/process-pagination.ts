import type { DnaTimelineItem } from "./dna-history";

export const TIMELINE_LOCAL_BATCH_SIZE = 100;

/** Nejdřív projde již staženou osu po lokálních dávkách; síť přichází až za ní. */
export function localTimelinePage(rows: DnaTimelineItem[], visible: number) {
  const start = Math.max(0, rows.length - visible);
  return { rows: rows.slice(start), hasOlderLocal: start > 0 };
}
