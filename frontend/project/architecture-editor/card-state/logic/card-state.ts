// Stav karty Editoru architektury ve stejném jazyce jako Studio (docs/studio.md §2): plán, staví se, hotovo,
// ověřeno, díra. Nic se tu neodvozuje po svém: strom, fakta i pravidla jsou Studia (`studio-tree`, `studio-facts`,
// `studio-status`, `card-view`); tady se jen přiřadí uzlům grafu, aby plátno 2 (plán stránky) četlo stav stejně
// jako plátno Studia. Čistá logika bez Reactu.
import type { Graph } from "@/shared/types/logic/types";
import { buildStudioTree } from "@/project/studio/logic/studio-tree";
import { cardStatus, type StudioFacts, type StudioJourney, type StudioState } from "@/project/studio/logic/studio-status";
import { studioFacts, type StudioFactsInput } from "@/project/studio/logic/studio-facts";
import { STATE_LABEL, summaryLine } from "@/project/studio/studio-card/logic/card-view";
import type { GuardTally } from "@/project/studio/studio-guards/logic/guard-tally";
import type { WorktreeTally } from "@/project/studio/studio-worktree/logic/worktree-tally";

export type CardState = {
  state: StudioState; label: string;
  /** Souhrn dětí jednou větou jako pata karty Studia („2/3 stojí · 1 se staví“). */
  summary: string;
  /** Díry mapy karty a všech jejích potomků. */
  holes: number;
  /** Nálezy strážců karty a všech jejích potomků (součet, nejvážnější závažnost); `null` = žádný. */
  guards: GuardTally | null;
  /** Kolik z děr už některý worktree zavírá („3 díry · 1 v práci“). */
  holesInWork: number;
  /** Worktree karty a potomků (rám `--worktree`, odznak větve); `null` = ve worktree se tu nepracuje. */
  worktree: WorktreeTally | null;
};

/** Stav každého uzlu, který Studio zná (doména, stránka, sektor, komponenta); oblasti a komentáře stav nemají. */
export function cardStates(graph: Graph, facts: StudioFacts): Map<string, CardState> {
  const tree = buildStudioTree(graph);
  const states = new Map<string, CardState>();
  for (const item of tree.items.values()) {
    if (!item.node) continue;
    const status = cardStatus(tree, item, facts);
    states.set(item.id, { state: status.state, label: STATE_LABEL[status.state], summary: summaryLine(status.summary), holes: status.summary.holes, guards: status.guards,
      holesInWork: status.holesInWork, worktree: status.worktree });
  }
  return states;
}

export type CardLife = {
  states: Map<string, CardState>;
  /** Cesty zákazníka s posledním ověřením pro pohyb vazeb; null = odvození ještě není načtené. */
  journeys: StudioJourney[] | null;
};

/** Fakta Skutečnosti (uzavřené karty, aktivní nároky, díry, cesty s `lastRun`, nálezy strážců, práce ve worktree) → stavy karet a cesty pro pohyb. */
export function cardLife(input: StudioFactsInput): CardLife {
  const facts = studioFacts(input);
  return { states: cardStates(input.graph, facts), journeys: input.derived ? facts.journeys : null };
}
