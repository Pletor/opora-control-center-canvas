// Pohyb vazeb Editoru stránky jen ze skutečného stavu (docs/zive-zobrazeni-a-knihovna.md §1 a §3), se stejnými
// pravidly a časy jako pohyb Skutečnosti ve Studiu (`studio-motion/motion-plan.ts`, `run-events.ts`): trvale tečky
// po vazbách, jejichž karta na jednom konci se staví; jednou tečka po vazbách nově ověřené cesty a puls jejích karet;
// staticky červená tečka s křížkem na vazbě prvního selhání; po dobu běhu cesty (`running`, docs/brana-cesty.md §3a)
// obíhají tečky po vazbách aktuálního přechodu. Rozdíl proti Studiu je jen v tom, kde přechod cesty
// leží: na plátně stránky jsou karty uzly grafu (ne souhrnné vazby úrovně), takže přechod `from → to` mezi kroky
// realizuje každá vazba `next`, jejíž zdroj patří stránce kroku `from` a cíl stránce kroku `to` (podstránka na plátně
// patří sama sobě, ostatní karty otevřené stránce). Čistá logika bez Reactu.
import type { CanvasNode, GraphEdge } from "@/shared/types/logic/types";
import { canCarry } from "@/shared/edge-carries/logic/edge-carries";
import { FROM_NAV } from "../../../domain-map/logic/journeys";
import type { StudioLink } from "@/project/studio/logic/studio-level";
import type { StudioJourney, StudioState } from "@/project/studio/logic/studio-status";
import { levelMotion, type LevelFailure, type LevelPass, type LevelRunning, type LinkMotion } from "@/project/studio/studio-motion/logic/motion-plan";
import { runFailures, runningHops } from "@/project/studio/studio-motion/logic/run-events";

/** Karty otevřeného rozsahu, vazby mezi nimi a stránka rozsahu (null = rozsah mimo stránky). */
export type MapPlace = { cards: CanvasNode[]; edges: GraphEdge[]; pageId: string | null };
export type MapMotion = { links: Map<string, LinkMotion>; pulsing: Set<string> };
export type MapPass = { stamp: string; journey: StudioJourney };
type Hop = { from: string; to: string };

/** Stránka karty na plátně: podstránka je sama sebou, ostatní karty leží na otevřené stránce. */
export const pageOfCard = (card: Pick<CanvasNode, "id" | "site">, pageId: string | null) => (card.site?.kind === "page" ? card.id : pageId);

/** Vazby plátna (`next`), které realizují přechod mezi kroky; menu, neznámý krok nebo krok na téže stránce žádné. */
export function hopEdges(place: MapPlace, journey: StudioJourney, hop: Hop): string[] {
  const from = journey.stepPages.get(hop.from); const to = journey.stepPages.get(hop.to);
  if (!from || !to || from === FROM_NAV || to === FROM_NAV || from === to) return [];
  const byId = new Map(place.cards.map((card) => [card.id, card]));
  return place.edges.filter((edge) => {
    const source = byId.get(edge.source); const target = byId.get(edge.target);
    return canCarry(edge) && !!source && !!target && pageOfCard(source, place.pageId) === from && pageOfCard(target, place.pageId) === to;
  }).map((edge) => edge.id);
}

/** Vazby trasy v pořadí přechodů (každá jednou). */
export function routeEdges(place: MapPlace, journey: StudioJourney): string[] {
  const route: string[] = [];
  for (const hop of journey.derived?.segments ?? []) for (const id of hopEdges(place, journey, hop)) if (!route.includes(id)) route.push(id);
  return route;
}

/** Vazba plátna jako souhrnná vazba Studia o jedné hraně, aby šla pravidly `levelMotion` beze změny. */
const asLink = (edge: GraphEdge): StudioLink => ({ id: edge.id, source: edge.source, target: edge.target, count: 1, carries: edge.carries ?? "unspecified", kinds: {}, edgeIds: [edge.id] });

/** Pohyb vazeb plátna a karty k jednorázovému pulzu (konce vazeb trasy a podstránky, které jsou krokem cesty). */
export function mapMotion(place: MapPlace, states: ReadonlyMap<string, StudioState>, passes: MapPass[], journeys: StudioJourney[] | null): MapMotion {
  const ids = new Set(place.cards.map((card) => card.id));
  const edges = place.edges.filter((edge) => canCarry(edge) && ids.has(edge.source) && ids.has(edge.target));
  const scoped = { ...place, edges };
  const byId = new Map(edges.map((edge) => [edge.id, edge]));
  const pulsing = new Set<string>();
  const levelPasses: LevelPass[] = passes.map(({ stamp, journey }) => {
    const links = routeEdges(scoped, journey);
    for (const id of links) { pulsing.add(byId.get(id)!.source); pulsing.add(byId.get(id)!.target); }
    for (const page of journey.pages) if (ids.has(page)) pulsing.add(page);
    return { stamp, links };
  });
  const failures: LevelFailure[] = (journeys ? runFailures(journeys) : []).flatMap((failure) =>
    hopEdges(scoped, failure.journey, failure).map((linkId) => ({ linkId, title: failure.title })));
  const running: LevelRunning[] = (journeys ? runningHops(journeys) : []).flatMap((hop) =>
    hopEdges(scoped, hop.journey, hop).map((linkId) => ({ linkId, title: hop.title })));
  return { links: levelMotion({ links: edges.map(asLink), states: new Map(states), passes: levelPasses, failures, running }), pulsing };
}
