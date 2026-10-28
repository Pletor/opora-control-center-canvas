// Fakta pro stav karet Studia ze zdrojů vrstvy Skutečnost (docs/studio.md §1): uzavření karet z Desktop stavu
// (`done.confirmed`), aktivní nároky práce z `GET /api/project-architecture/work-status` (lease `active`, relace
// asistenta `running`), nálezy kontroly mapy, nálezy strážců z agent-state a cesty zákazníka domén s odvozením backendu (`lastRun`). Jen čte.
import type { Graph } from "@/shared/types/logic/types";
import type { WorkStatus, LiveSession } from "@/project/architecture-editor/live-status/logic/live-model";
import type { MapCheck } from "@/project/architecture-editor/domain-map/map-check/logic/map-check";
import { derivedForDomain, type DerivedJourney } from "@/project/architecture-editor/domain-map/logic/derived-journeys";
import { FROM_NAV } from "@/project/architecture-editor/domain-map/logic/journeys";
import type { StudioFacts, StudioJourney } from "./studio-status";
import type { GuardTally } from "../studio-guards/logic/guard-tally";

/** Karty, na kterých právě někdo pracuje: aktivní lease nebo běžící relace asistenta s kartou, ve všech worktree i na mainu. */
export function buildingNodes(status: WorkStatus | null): Set<string> {
  const ids = new Set<string>();
  if (!status) return ids;
  const live = (session: LiveSession) => (session.source === "lease" ? session.state === "active" : session.state === "running");
  const sessions = [...status.domains.flatMap((domain) => domain.worktrees), ...status.unassigned].flatMap((worktree) => worktree.sessions).concat(status.mainSessions);
  for (const session of sessions) if (session.nodeId && live(session)) ids.add(session.nodeId);
  return ids;
}

/** Nálezy po uzlech: `nodeId` přímo, hrana zdroji, cesta doméně, ve které cesta je. */
export function holesByNode(check: MapCheck | null, graph: Graph): Map<string, string[]> {
  const holes = new Map<string, string[]>();
  if (!check) return holes;
  const domainOfJourney = new Map<string, string>();
  for (const node of graph.nodes) if (node.site?.kind === "application") for (const journey of node.site.journeys ?? []) domainOfJourney.set(journey.id, node.id);
  for (const finding of check.findings) {
    const nodeId = finding.nodeId ?? (finding.edgeId ? graph.edges.find((edge) => edge.id === finding.edgeId)?.source : undefined)
      ?? (finding.journeyId ? domainOfJourney.get(finding.journeyId) : undefined);
    if (!nodeId) continue;
    holes.set(nodeId, [...(holes.get(nodeId) ?? []), finding.message]);
  }
  return holes;
}

/** Cesty všech domén: stránky kroků (bez „nav“) a odvození podle id cesty v doméně. */
export function studioJourneys(graph: Graph, derived: DerivedJourney[] | null): StudioJourney[] {
  return graph.nodes.flatMap((node) => {
    if (node.site?.kind !== "application") return [];
    const runs = derivedForDomain(derived ?? [], node.id);
    return (node.site.journeys ?? []).map((journey) => ({
      id: journey.id, name: journey.name || journey.id, domainId: node.id,
      pages: new Set(journey.steps.map((step) => step.page).filter((page) => page !== FROM_NAV)),
      stepPages: new Map(journey.steps.map((step) => [step.id, step.page])), derived: runs.get(journey.id),
    }));
  });
}

/** Vstup faktů; `guards` = nálezy strážců po kartách (`useCardGuards`), chybí = bez odznaků strážců. */
export type StudioFactsInput = { graph: Graph; doneIds: Iterable<string>; work: WorkStatus | null; check: MapCheck | null; derived: DerivedJourney[] | null; guards?: Map<string, GuardTally> };

export function studioFacts(input: StudioFactsInput): StudioFacts {
  return { done: new Set(input.doneIds), building: buildingNodes(input.work), holes: holesByNode(input.check, input.graph), journeys: studioJourneys(input.graph, input.derived),
    guards: input.guards };
}
