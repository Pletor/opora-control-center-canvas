import type { HeartBatch } from "./heart-api";

/** Cena dávky v USD česky: „0,12 USD“, pod půl centu „< 0,01 USD“, neznámá „—“. */
export function formatCost(costUsd: number | null | undefined): string {
  if (typeof costUsd !== "number" || !Number.isFinite(costUsd) || costUsd < 0) return "—";
  if (costUsd > 0 && costUsd < 0.005) return "< 0,01 USD";
  return `${costUsd.toFixed(2).replace(".", ",")} USD`;
}

const STATUS: Record<string, string> = { rate_limited: "Limit předplatného", error: "Dávka skončila chybou", timeout: "Dávce vypršel čas" };

export type BatchRow = { key: string; summary: string; cost: string };

/** Dávky (deník je od nejstarší) → řádky od nejnovější: shrnutí srdce, jinak stav dávky, a cena. */
export function batchRows(batches: HeartBatch[]): BatchRow[] {
  return [...batches].reverse().map((entry, index) => ({
    key: `${entry.at}-${index}`,
    summary: entry.summary?.trim() || STATUS[entry.status] || "Bez shrnutí",
    cost: formatCost(entry.costUsd),
  }));
}
