// Cesty zákazníka jako vodorovné dráhy pod plátnem Studia na úrovni domény (docs/studio.md, docs/architektura-pro-agenty.md §7). Čistá logika bez Reactu:
// z cest domény (`site.journeys`), stránek a odvození backendu (`derivedJourneys`, §6 a docs/brana-cesty.md §4) sestaví
// zastávky a přechody s realizací a stavem podle posledního ověření. Popisky stránek a signál `via` sdílí s trychtýřem.
import type { ApplicationSite, CanvasNode, CustomerJourney } from "@/shared/types/logic/types";
import { FROM_NAV, previousStepId, stepName, stepPageLabel, stepSignal } from "@/project/architecture-editor/domain-site/logic/journeys";
import type { DerivedJourney } from "@/project/architecture-editor/domain-site/logic/derived-journeys";

/** Stav přechodu podle posledního dokladu: prošel, neprošel (první neúspěšný), zastaralý doklad, nebo bez důkazu. */
export type TransitionState = "passed" | "failed" | "stale" | "unverified";
/** Zastávka dráhy: stránka kroku (název + cesta), menu, nebo stránka, která v mapě chybí. `pageId` jen u existující stránky. */
export type LaneStop = { stepId: string; role: string; title: string; path: string; pageId: string | null; missing: boolean };
/** Přechod do zastávky: signál `via` jako věta, odbočka, realizace na mapě (`realized` null = odvození chybí) a stav ověření. */
export type LaneTransition = {
  from: string; to: string; signal: string | null; missingSection: string | null; branchFrom: string | null;
  realized: boolean | null; line: string; state: TransitionState; reason: string | null;
};
/** Dráha jedné cesty: zastávky v pořadí člověka, `transitions[i]` vede do `stops[i + 1]`. */
export type StudioLane = {
  journey: CustomerJourney; derived: DerivedJourney | undefined; broken: string | null;
  stops: LaneStop[]; transitions: LaneTransition[];
};

export const TRANSITION_TEXT: Record<TransitionState, string> = {
  passed: "prošel", failed: "neprošel", stale: "ověření zastaralé", unverified: "neověřeno",
};

/** Stav přechodu `from → to` podle `lastRun`: zastaralý doklad platí pro všechny přechody, prošlý doklad taky; u neprošlého
 * je „neprošel“ jen první neúspěšný přechod (`firstFailure`), ostatní doklad nedokazuje. */
export function transitionState(derived: DerivedJourney | undefined, from: string, to: string): TransitionState {
  const run = derived?.lastRun;
  if (!run || derived?.broken) return "unverified";
  if (run.stale) return "stale";
  if (run.passed) return "passed";
  return run.firstFailure?.from === from && run.firstFailure.to === to ? "failed" : "unverified";
}

function stop(journey: CustomerJourney, index: number, pages: CanvasNode[]): LaneStop {
  const step = journey.steps[index];
  const role = step.label ?? `${index + 1}. krok`;
  if (step.page === FROM_NAV) return { stepId: step.id, role, title: "Menu", path: "nav", pageId: null, missing: false };
  const page = pages.find((item) => item.id === step.page);
  const { label, missing } = stepPageLabel(step.page, pages);
  return { stepId: step.id, role, title: label, path: page?.site?.kind === "page" ? page.site.path : "", pageId: page ? page.id : null, missing };
}

function transition(journey: CustomerJourney, index: number, pages: CanvasNode[], derived: DerivedJourney | undefined): LaneTransition {
  const to = journey.steps[index].id;
  const from = previousStepId(journey, index) ?? journey.steps[index - 1].id;
  const signal = stepSignal(journey, index, pages);
  const segment = derived?.segments.find((item) => item.from === from && item.to === to);
  const state = transitionState(derived, from, to);
  const first = derived?.lastRun?.firstFailure;
  return {
    from, to, signal: signal?.text ?? null, missingSection: signal?.missingSection ?? null,
    branchFrom: from !== journey.steps[index - 1].id ? stepName(journey, from) : null,
    realized: segment ? segment.realized : null, line: segment?.line ?? "", state,
    reason: state === "failed" ? first?.reason ?? null : null,
  };
}

/** Dráhy všech cest domény v pořadí `site.journeys`; `derived` = odvození cest této domény podle id. */
export function studioLanes(site: ApplicationSite | undefined, pages: CanvasNode[], derived: ReadonlyMap<string, DerivedJourney>): StudioLane[] {
  return (site?.journeys ?? []).map((journey) => {
    const run = derived.get(journey.id);
    return {
      journey, derived: run, broken: run?.broken ?? null,
      stops: journey.steps.map((_, index) => stop(journey, index, pages)),
      transitions: journey.steps.slice(1).map((_, index) => transition(journey, index + 1, pages, run)),
    };
  });
}
