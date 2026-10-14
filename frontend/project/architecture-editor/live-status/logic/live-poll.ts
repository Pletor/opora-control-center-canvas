// Rytmus a paměť živého čtení (docs/domeny-a-worktree.md §10): stav práce každých 10 s v detailu
// domény a 30 s na přehledu, web každých 60 s (backend drží cache 60 s). Po chybě se čte s odstupem
// 10 → 20 → 60 s a poslední data zůstávají s poznámkou „údaj z 12:03“.

export const WORK_INTERVAL_MS = { detail: 10_000, landing: 30_000 } as const;
export const WEB_INTERVAL_MS = 60_000;
const BACKOFF_MS = [10_000, 20_000, 60_000];

/** Pauza před dalším kolem: bez chyby základní interval, po chybách odstup (nikdy kratší než základ). */
export function liveDelay(baseMs: number, failures: number): number {
  if (failures <= 0) return baseMs;
  return Math.max(baseMs, BACKOFF_MS[Math.min(failures, BACKOFF_MS.length) - 1]);
}

export type LiveSlot<T> = { data: T | null; failures: number; error: string; updatedAt: number | null; loading: boolean };

export const emptySlot = <T>(): LiveSlot<T> => ({ data: null, failures: 0, error: "", updatedAt: null, loading: false });

export const slotLoading = <T>(slot: LiveSlot<T>): LiveSlot<T> => ({ ...slot, loading: true });

export const slotLoaded = <T>(slot: LiveSlot<T>, data: T, now: number): LiveSlot<T> => ({ ...slot, data, failures: 0, error: "", updatedAt: now, loading: false });

/** Chyba nechá poslední data; jen přičte selhání (odstup) a zapamatuje text chyby. */
export const slotFailed = <T>(slot: LiveSlot<T>, error: string): LiveSlot<T> => ({ ...slot, failures: slot.failures + 1, error, loading: false });

export const isStale = (slot: LiveSlot<unknown>) => slot.failures > 0 && slot.data !== null;

/** „údaj z 12:03“ u zastaralých dat, jinak prázdné. */
export function staleNote(slot: LiveSlot<unknown>): string {
  if (!isStale(slot) || slot.updatedAt === null) return "";
  const moment = new Date(slot.updatedAt);
  return `údaj z ${String(moment.getHours()).padStart(2, "0")}:${String(moment.getMinutes()).padStart(2, "0")}`;
}
