// Úsek cesty zákazníka jedné stránky (docs/cesta-zakaznika-a-brief.md §5.1) pro zadání rozkladu stránky: pro každý krok
// každé cesty domény, který vede na stránku, odkud zákazník přišel, co se tu má posunout a kam pokračuje.
// Čistá logika bez Reactu, test vedle. Cesty se tu jen čtou.
import type { ApplicationSite, CanvasNode, CustomerJourney } from "@/shared/types/logic/types";
import { FROM_NAV, previousStepId, stepPageLabel, stepSignal } from "../../../domain-site/logic/journeys";
import { derivedStepState, type DerivedJourney } from "../../../domain-site/logic/derived-journeys";
import { verificationBadge, type VerificationBadge } from "../../../domain-site/logic/journey-verification";

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
