// Stav a ikona karty Editoru architektury ve stejném jazyce jako Studio (docs/studio.md §2): plán, staví se, hotovo,
// ověřeno, díra. Nic se tu neodvozuje po svém: strom, fakta i pravidla jsou Studia (`studio-tree`, `studio-facts`,
// `studio-status`, `card-view`); tady se jen přiřadí uzlům grafu, aby Editor stránky i Mapa domény četly stav stejně
// jako plátno Studia. Čistá logika bez Reactu.
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import type { WorkStatus } from "../../live-status/logic/live-model";
import type { MapCheck } from "../../domain-map/map-check/logic/map-check";
import type { DerivedJourney } from "../../domain-map/logic/derived-journeys";
import { buildStudioTree, type StudioKind } from "@/project/studio/logic/studio-tree";
import { cardStatus, type StudioFacts, type StudioJourney, type StudioState } from "@/project/studio/logic/studio-status";
import { studioFacts } from "@/project/studio/logic/studio-facts";
import { iconFor, STATE_LABEL, summaryLine } from "@/project/studio/studio-card/logic/card-view";
import type { StudioIconName } from "@/project/studio/studio-card/logic/studio-icons";

export type CardState = {
  state: StudioState; label: string;
  /** Souhrn dětí jednou větou jako pata karty Studia („2/3 stojí · 1 se staví“). */
  summary: string;
  /** Díry mapy karty a všech jejích potomků. */
  holes: number;
};

/** Stav každého uzlu, který Studio zná (doména, stránka, sektor, komponenta); oblasti a komentáře stav nemají. */
export function cardStates(graph: Graph, facts: StudioFacts): Map<string, CardState> {
  const tree = buildStudioTree(graph);
  const states = new Map<string, CardState>();
  for (const item of tree.items.values()) {
    if (!item.node) continue;
    const status = cardStatus(tree, item, facts);
    states.set(item.id, { state: status.state, label: STATE_LABEL[status.state], summary: summaryLine(status.summary), holes: status.summary.holes });
  }
  return states;
}

export type CardLife = {
  states: Map<string, CardState>;
  /** Cesty zákazníka s posledním ověřením pro pohyb vazeb; null = odvození ještě není načtené. */
  journeys: StudioJourney[] | null;
};

/** Fakta Skutečnosti (uzavřené karty, aktivní nároky, díry, cesty s `lastRun`) → stavy karet a cesty pro pohyb. */
export function cardLife(input: { graph: Graph; doneIds: Iterable<string>; work: WorkStatus | null; check: MapCheck | null; derived: DerivedJourney[] | null }): CardLife {
  const facts = studioFacts(input);
  return { states: cardStates(input.graph, facts), journeys: input.derived ? facts.journeys : null };
}

/** Ikona druhu karty (Lucide jako ve Studiu): doména, stránka, sektor jako seznam, komponenta podle vrstvy. */
export function cardIcon(node: CanvasNode): StudioIconName {
  const kind: StudioKind = node.site?.kind === "application" ? "domain" : node.site?.kind === "page" ? "page" : node.kind === "sector" ? "section" : "component";
  return iconFor({ id: node.id, kind, name: node.name, purpose: node.purpose, node, pageId: null, domainId: null });
}

/** „1 díra“, „3 díry“, „5 děr“ jako odznak v patě karty Studia. */
export const holesLabel = (holes: number) => `${holes} ${holes === 1 ? "díra" : holes < 5 ? "díry" : "děr"}`;
