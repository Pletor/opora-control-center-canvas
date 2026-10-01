// Pravidla fronty briefů pro kapitoly módu Text, bez Reactu. Brief jedné karty drží zámek plátna a na
// git projektu spouští desítky volání gitu, proto se načítá jen pro rozbalené kapitoly a po jedné.
// Tenhle modul říká, které id je na řadě, co ukázat během obnovy a jak přečíst levný souhrn paměti;
// síť a časovače drží `use-chapter-overviews.ts`.
import type { ChapterWork, OverviewEntry } from "@/editor/node-detail/agent-summary/logic/agent-summary";

type UnknownRecord = Record<string, unknown>;
const record = (value: unknown): UnknownRecord =>
  value !== null && typeof value === "object" && !Array.isArray(value) ? (value as UnknownRecord) : {};

/** Levný souhrn z odpovědi serveru; položka s neplatným tvarem se vynechá, ne dopočítá. */
export function worksFrom(value: unknown): { works: Record<string, ChapterWork>; readOnly: boolean } {
  const body = record(value);
  const works: Record<string, ChapterWork> = {};
  for (const [nodeId, raw] of Object.entries(record(body.items))) {
    const item = record(raw);
    if (typeof item.filled !== "number" || !Number.isFinite(item.filled)) continue;
    works[nodeId] = {
      filled: Math.max(0, Math.floor(item.filled)),
      by: item.by === "agent" ? "agent" : "human",
      updatedAt: typeof item.updatedAt === "string" ? item.updatedAt : "",
    };
  }
  return { works, readOnly: body.readOnly === true };
}

/**
 * První rozbalené id (v pořadí kapitol), které nemá záznam z aktuální generace obnovy. Chyba se
 * počítá jako záznam: fronta ji v téže generaci znovu nezkouší, až po obnovení.
 */
export function nextStale(
  expandedIds: readonly string[],
  loadedAt: ReadonlyMap<string, number>,
  generation: number,
): string | null {
  return expandedIds.find((id) => loadedAt.get(id) !== generation) ?? null;
}

/** Všechna id čekající ve frontě: jen rozbalená a bez záznamu z aktuální generace. */
export function staleIds(
  expandedIds: readonly string[],
  loadedAt: ReadonlyMap<string, number>,
  generation: number,
): string[] {
  return expandedIds.filter((id) => loadedAt.get(id) !== generation);
}

/** Čekající záznamy přepne na „loading“; starý přehled zůstává vidět, dokud nepřijde nový. */
export function markLoading(entries: Record<string, OverviewEntry>, ids: readonly string[]): Record<string, OverviewEntry> {
  if (!ids.some((id) => entries[id]?.status !== "loading")) return entries;
  const next = { ...entries };
  for (const id of ids) next[id] = { status: "loading", overview: entries[id]?.overview ?? null };
  return next;
}
