// Stránka zná své cesty: na kterých cestách zákazníka aplikace leží, v jaké roli a k jakému posunu slouží
// (docs/architektura-pro-agenty.md §3.2). Čistá logika bez Reactu; karta a formulář stránky to jen ukazují, cesty se mění v trychtýři cesty.
import type { ApplicationSite } from "@/shared/types/logic/types";

/** Role stránky v jedné cestě: krok `step` (pořadí od 1) s rolí `label` a posunem `shift`, když je člověk zadal. */
export type PageJourneyRole = { journeyId: string; journeyName: string; stepId: string; step: number; label?: string; shift?: string };

/** Všechny kroky všech cest aplikace, které vedou na stránku `pageId`, v pořadí cest a kroků. */
export function journeysOfPage(site: ApplicationSite | undefined, pageId: string): PageJourneyRole[] {
  return (site?.journeys ?? []).flatMap((journey) => journey.steps.flatMap((step, index) => step.page === pageId
    ? [{ journeyId: journey.id, journeyName: journey.name, stepId: step.id, step: index + 1,
      ...(step.label ? { label: step.label } : {}), ...(step.shift ? { shift: step.shift } : {}) }]
    : []));
}

/** Krátký popis role: „Prodej kurzu · Upsell (krok 4) – chce víc“, bez role jen „Prodej kurzu · krok 4“, posun jen když je. */
export function pageJourneyText(role: PageJourneyRole): string {
  return role.journeyName + " · " + (role.label ? `${role.label} (krok ${role.step})` : `krok ${role.step}`)
    + (role.shift ? " – " + role.shift : "");
}
