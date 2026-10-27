// Úsek cesty zákazníka aktivní stránky v Editoru stránky (docs/cesta-zakaznika-a-brief.md §5.1): pro každý krok každé
// cesty domény, který vede na stránku, odkud zákazník přišel, co se tu má posunout a kam pokračuje; pod tím sekce
// stránky s počtem komponent, které je realizují (`card.section`). Čistá logika bez Reactu, test vedle.
// Cesty se tu jen čtou: mění se v trychtýři na Mapě domény.
import type { ApplicationSite, CanvasNode, CustomerJourney, Graph } from "@/shared/types/logic/types";
import { FROM_NAV, previousStepId, stepPageLabel, stepSignal } from "../../../domain-map/logic/journeys";
import { derivedStepState, type DerivedJourney } from "../../../domain-map/logic/derived-journeys";
import { verificationBadge, type VerificationBadge } from "../../../domain-map/logic/journey-verification";
import { SECTION_ROLE_LABELS } from "../../../domain-map/logic/page-site";
import { activePageId } from "../../project-tree/logic/project-tree-model";

/** Sousední krok: role, stránka (`pageId` jen když jde otevřít), signál přechodu (`signal` = jak se jde z předchozího
 * do dalšího kroku), odbočka a chybějící vazba na mapě. */
export type SliceNeighbour = {
  stepId: string; role: string; pageId: string | null; pageLabel: string; missing: boolean;
  signal: { text: string; missingSection: string | null } | null; branch: boolean; unrealized: string | null;
};
/** Jeden krok cesty na aktivní stránce: proměna cesty (A/B, aktér), role kroku, posun, námitka a sousedé. */
export type PageSlice = {
  journeyId: string; journeyName: string; actor?: string; pointA?: string; pointB?: string; broken?: string;
  stepId: string; step: number; stepCount: number; role: string; shift?: string; objection?: string;
  /** Jak zákazník přijde na první krok (jen `open`); u dalších kroků nese signál `from`. */
  entry: string | null; from: SliceNeighbour | null; next: SliceNeighbour[];
  /** Odznak ověření cesty (poslední doklad přehrání), jen když backend cestu odvodil a není rozbitá. */
  verification?: VerificationBadge;
};
/** Štítek sekce v pruhu sekcí: role, název, čím posouvá a kolik komponent stránky ji realizuje. */
export type SectionChip = { id: string; role: string; name: string; moves?: string; components: number };

function roleOf(journey: CustomerJourney, index: number): string {
  return journey.steps[index].label ?? `${index + 1}. krok`;
}

function neighbour(journey: CustomerJourney, index: number, signalIndex: number, branch: boolean, pages: CanvasNode[], derived: DerivedJourney | undefined): SliceNeighbour {
  const step = journey.steps[index];
  const page = stepPageLabel(step.page, pages);
  const into = journey.steps[signalIndex];
  return { stepId: step.id, role: roleOf(journey, index), pageId: step.page === FROM_NAV || page.missing ? null : step.page, pageLabel: page.label,
    missing: page.missing, signal: stepSignal(journey, signalIndex, pages), branch, unrealized: derivedStepState(derived, into.id).unrealized };
}

/** Kroky všech cest domény, které vedou na `pageId`, v pořadí cest a kroků; stránka na stejné cestě dvakrát = dva úseky. */
export function pageSlices(site: ApplicationSite | undefined, pageId: string, pages: CanvasNode[], derived: ReadonlyMap<string, DerivedJourney> = new Map()): PageSlice[] {
  return (site?.journeys ?? []).flatMap((journey) => {
    const facts = derived.get(journey.id);
    const badge = verificationBadge(facts);
    return journey.steps.flatMap((step, index): PageSlice[] => {
      if (step.page !== pageId) return [];
      const before = previousStepId(journey, index);
      const fromIndex = journey.steps.findIndex((other) => other.id === before);
      const next = journey.steps.flatMap((_, later) => later > index && previousStepId(journey, later) === step.id
        ? [neighbour(journey, later, later, later !== index + 1, pages, facts)] : []);
      return [{ journeyId: journey.id, journeyName: journey.name,
        ...(journey.actor ? { actor: journey.actor } : {}), ...(journey.pointA ? { pointA: journey.pointA } : {}),
        ...(journey.pointB ? { pointB: journey.pointB } : {}), ...(facts?.broken ? { broken: facts.broken } : {}),
        stepId: step.id, step: index + 1, stepCount: journey.steps.length, role: roleOf(journey, index),
        ...(step.shift ? { shift: step.shift } : {}), ...(step.objection ? { objection: step.objection } : {}),
        entry: index === 0 && step.via?.do === "open" ? "otevře stránku přímo" : null,
        from: fromIndex < 0 ? null : neighbour(journey, fromIndex, index, fromIndex !== index - 1, pages, facts), next,
        ...(badge ? { verification: badge } : {}) }];
    });
  });
}

/** Sekce stránky v uloženém pořadí s počtem komponent, jejichž nejbližší stránka je `pageId` a které sekci realizují. */
export function sectionChips(graph: Graph, pageId: string): SectionChip[] {
  const page = graph.nodes.find((node) => node.id === pageId);
  const sections = page?.site?.kind === "page" ? page.site.sections ?? [] : [];
  if (!sections.length) return [];
  const counts = new Map<string, number>();
  for (const node of graph.nodes) {
    const section = node.kind === "node" && node.id !== pageId ? node.card?.section : undefined;
    if (section && activePageId(graph, node.id) === pageId) counts.set(section, (counts.get(section) ?? 0) + 1);
  }
  return sections.map((section) => ({ id: section.id, role: SECTION_ROLE_LABELS[section.role] ?? section.role, name: section.name,
    ...(section.moves ? { moves: section.moves } : {}), components: counts.get(section.id) ?? 0 }));
}
