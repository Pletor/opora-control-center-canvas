// Otevřené nálezy strážců na kartách Skutečnosti (docs/strazci.md §5 „Studio a Architektura“): počet a nejvážnější
// závažnost. Zdroj je jen agent-state `cards[].guardFindings` (bez strážce mapy, cesty jsou díry mapy). Rodič ve
// fraktálu sčítá nálezy dětí stejně jako díry. Čistá logika bez Reactu.
import type { AgentCardStage, GuardSeverity } from "@/hub/oporahub-agent-state/logic/agent-state";
import { GUARD_LABEL } from "@/project/architecture-editor/element-detail/logic/work-view";

export type GuardTally = { count: number; severity: GuardSeverity };

const RANK: Record<GuardSeverity, number> = { info: 0, warn: 1, block: 2 };

/** Nálezy po kartách; karta bez nálezu (nebo s nulou) v mapě není. Chybějící `cards` = prázdná mapa. */
export function guardsByNode(cards: readonly AgentCardStage[] | null | undefined): Map<string, GuardTally> {
  const guards = new Map<string, GuardTally>();
  for (const card of cards ?? []) {
    const found = card.guardFindings;
    if (found && found.count > 0) guards.set(card.nodeId, { count: found.count, severity: found.severity });
  }
  return guards;
}

/** Otisk nálezů pro memoizaci (JSON záznamů mapy); bez nálezu prázdný řetězec. */
export const guardsKey = (guards: Map<string, GuardTally>) => guards.size ? JSON.stringify([...guards]) : "";

/** Součet nálezů a nejvážnější závažnost; bez jediného nálezu `null`. */
export function sumGuards(tallies: Iterable<GuardTally | null | undefined>): GuardTally | null {
  let total: GuardTally | null = null;
  for (const tally of tallies) {
    if (!tally || tally.count <= 0) continue;
    total = !total ? { ...tally }
      : { count: total.count + tally.count, severity: RANK[tally.severity] > RANK[total.severity] ? tally.severity : total.severity };
  }
  return total;
}

const findings = (count: number) => `${count} ${count === 1 ? "nález" : count < 5 ? "nálezy" : "nálezů"}`;

/** Věta pro title a čtečku: „Strážci: 2 nálezy (blokuje)“. */
export const guardLabel = (tally: GuardTally) => `Strážci: ${findings(tally.count)} (${GUARD_LABEL[tally.severity]})`;
