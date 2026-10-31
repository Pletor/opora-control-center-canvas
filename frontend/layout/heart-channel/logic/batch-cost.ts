import type { HeartBatch } from "./heart-api";
import { batchRange, type StepRange } from "./heart-live";

/** Cena dávky v USD česky: „0,12 USD“, pod půl centu „< 0,01 USD“, neznámá „—“. */
export function formatCost(costUsd: number | null | undefined): string {
  if (typeof costUsd !== "number" || !Number.isFinite(costUsd) || costUsd < 0) return "—";
  if (costUsd > 0 && costUsd < 0.005) return "< 0,01 USD";
  return `${costUsd.toFixed(2).replace(".", ",")} USD`;
}

const STATUS: Record<string, string> = { rate_limited: "Limit předplatného", error: "Dávka skončila chybou", timeout: "Dávce vypršel čas" };

/** `range` = rozsah kroků dávky v záznamu činnosti; bez trvání `null` (řádek se nerozbalí). */
export type BatchRow = { key: string; summary: string; cost: string; range: StepRange | null };

/** Dávky (deník je od nejstarší) → řádky od nejnovější: shrnutí srdce, jinak stav dávky, cena a rozsah kroků. */
export function batchRows(batches: HeartBatch[]): BatchRow[] {
  return [...batches].reverse().map((entry, index) => ({
    key: entry.at || String(index),  // podle začátku, aby rozbalený řádek přežil příchod nové dávky
    summary: entry.summary?.trim() || STATUS[entry.status] || "Bez shrnutí",
    cost: formatCost(entry.costUsd),
    range: batchRange(entry),
  }));
}
