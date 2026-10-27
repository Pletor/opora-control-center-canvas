// Události ověření cest pro pohyb Skutečnosti (docs/studio.md §2): co právě prošlo a kde cesta spadla. Průchod se
// ukáže jen při změně oproti předchozímu stavu (nový `lastRun.at`, prošlo, není zastaralé); první načtení stránky
// nastaví jen výchozí otisky a nic nepřehraje. Selhání je stav, ne událost: dokud poslední doklad neprošel, nese
// vazba `firstFailure` zastavenou červenou tečku. Čistá logika bez Reactu.
import type { StudioJourney } from "../../logic/studio-status";

/** Id cesty je jedinečné jen v doméně. */
export const journeyKey = (journey: Pick<StudioJourney, "domainId" | "id">) => `${journey.domainId}/${journey.id}`;

/** Otisk posledního dokladu každé cesty (`at`, prázdný = cesta doklad nemá). */
export type RunStamps = Map<string, string>;

export function runStamps(journeys: StudioJourney[]): RunStamps {
  return new Map(journeys.map((journey) => [journeyKey(journey), journey.derived?.lastRun?.at ?? ""]));
}

/** Cesty, jejichž doklad se od minula změnil a je prošlý a čerstvý; bez minulého otisku (první načtení) žádné. */
export function freshPasses(previous: RunStamps | null, journeys: StudioJourney[]): StudioJourney[] {
  if (!previous) return [];
  return journeys.filter((journey) => {
    const run = journey.derived?.lastRun;
    return !!run && run.passed && !run.stale && previous.get(journeyKey(journey)) !== run.at;
  });
}

export type RunFailure = { journey: StudioJourney; from: string; to: string; title: string };

/** Neprošlé cesty s prvním neúspěšným přechodem a větou do tooltipu (cesta, přechod, důvod, případně zastaralost). */
export function runFailures(journeys: StudioJourney[]): RunFailure[] {
  return journeys.flatMap((journey) => {
    const run = journey.derived?.lastRun;
    const first = run && !run.passed ? run.firstFailure : undefined;
    if (!run || !first) return [];
    const reason = first.reason ? `: ${first.reason}` : "";
    const stale = run.stale ? " (doklad je starší než mapa)" : "";
    return [{ journey, from: first.from, to: first.to, title: `Cesta ${journey.name} spadla na přechodu ${first.from} → ${first.to}${reason}${stale}` }];
  });
}
