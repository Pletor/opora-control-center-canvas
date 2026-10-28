// Stav a ikona karty Editoru architektury ve stejném jazyce jako Studio (docs/studio.md §2): plán, staví se, hotovo,
// ověřeno, díra. Nic se tu neodvozuje po svém: strom, fakta i pravidla jsou Studia (`studio-tree`, `studio-facts`,
// `studio-status`, `card-view`); tady se jen přiřadí uzlům grafu, aby Editor stránky i Mapa domény četly stav stejně
// jako plátno Studia. Čistá logika bez Reactu.
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { buildStudioTree, type StudioKind } from "@/project/studio/logic/studio-tree";
import { cardStatus, type StudioFacts, type StudioJourney, type StudioState } from "@/project/studio/logic/studio-status";
import { studioFacts, type StudioFactsInput } from "@/project/studio/logic/studio-facts";
import { holesLine, iconFor, STATE_LABEL, summaryLine } from "@/project/studio/studio-card/logic/card-view";
import type { StudioIconName } from "@/project/studio/studio-card/logic/studio-icons";
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

/** Ikona druhu karty (Lucide jako ve Studiu): doména, stránka, sektor jako seznam, komponenta podle vrstvy. */
export function cardIcon(node: CanvasNode): StudioIconName {
  const kind: StudioKind = node.site?.kind === "application" ? "domain" : node.site?.kind === "page" ? "page" : node.kind === "sector" ? "section" : "component";
  return iconFor({ id: node.id, kind, name: node.name, purpose: node.purpose, node, pageId: null, domainId: null });
}

/** „1 díra“, „3 díry“, „5 děr“, s prací ve worktree „3 díry · 1 v práci“, jako odznak v patě karty Studia. */
export const holesLabel = (holes: number, inWork = 0) => holesLine(holes, inWork);
