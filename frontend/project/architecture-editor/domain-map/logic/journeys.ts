// Cesty zákazníka A → B na aplikaci; čistá logika bez Reactu. Kontrakt: docs/architektura-pro-agenty.md §3.2.
// Člověk zadává jen název, začátek a cíl; kroky cesty se neukládají, odvodí je stroj. Prázdný seznam se neukládá.
import type { ApplicationSite, CanvasNode, CustomerJourney } from "@/shared/types/logic/types";

/** Nejvýš tolik cest na aplikaci povolí backend (`site_metadata.py`). */
export const MAX_JOURNEYS = 20;
/** Začátek cesty v navigaci (menu) místo konkrétní stránky. */
export const FROM_NAV = "nav";

/** Vrátí `site` s novým seznamem cest; prázdný seznam klíč `journeys` vynechá (backend prázdné pole odmítne). */
function withJourneys(site: ApplicationSite, journeys: CustomerJourney[]): ApplicationSite {
  const { journeys: _old, ...rest } = site;
  return journeys.length ? { ...rest, journeys } : rest;
}

/** Přidá cestu `cesta-N` z menu na první stránku; bez stránek nebo na 20 cestách nic neudělá. */
export function addJourney(site: ApplicationSite, pageIds: string[]): ApplicationSite {
  const journeys = site.journeys ?? [];
  if (journeys.length >= MAX_JOURNEYS || !pageIds.length) return site;
  const used = new Set(journeys.map((journey) => journey.id));
  let n = 1;
  while (used.has("cesta-" + n)) n += 1;
  return withJourneys(site, [...journeys, { id: "cesta-" + n, name: "Nová cesta", from: FROM_NAV, to: pageIds[pageIds.length - 1] }]);
}

/** Změní název, začátek nebo cíl cesty podle id; `id` se přepsat nedá. */
export function updateJourney(site: ApplicationSite, id: string, patch: Partial<Omit<CustomerJourney, "id">>): ApplicationSite {
  if (!site.journeys) return site;
  return withJourneys(site, site.journeys.map((journey) => (journey.id === id ? { ...journey, ...patch, id } : journey)));
}

/** Odebere cestu; po poslední zmizí i klíč `journeys`. */
export function removeJourney(site: ApplicationSite, id: string): ApplicationSite {
  if (!site.journeys) return site;
  return withJourneys(site, site.journeys.filter((journey) => journey.id !== id));
}

/** Před uložením oříznutý název; bez cest klíč zmizí. Prázdný název hlídá formulář (`required`). */
export function journeysForSave(site: ApplicationSite): ApplicationSite {
  return withJourneys(site, (site.journeys ?? []).map((journey) => ({ ...journey, name: journey.name.trim() })));
}

/** Proč cestu nejde uložit (začátek a cíl stejné), jinak `null`. Backend odmítne totéž. */
export function journeyProblem(journey: CustomerJourney): string | null {
  return journey.from === journey.to ? "Cesta musí vést na jinou stránku, než začíná." : null;
}

/** Popisek konce cesty: „Menu“, název stránky, nebo upozornění na stránku, která v mapě už není. */
export function journeyEndLabel(id: string, pages: Pick<CanvasNode, "id" | "name">[]): { label: string; missing: boolean } {
  if (id === FROM_NAV) return { label: "Menu", missing: false };
  const page = pages.find((candidate) => candidate.id === id);
  return page ? { label: page.name, missing: false } : { label: "chybí stránka " + id, missing: true };
}
