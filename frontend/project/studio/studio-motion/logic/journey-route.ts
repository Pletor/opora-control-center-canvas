// Trasa cesty zákazníka na aktuální úrovni Studia: přechod `from → to` mezi kroky se mapuje na stránky kroků a od nich
// na karty této úrovně (stránka sama nebo její předek, `cardInLevel`). Přechod leží na vazbě úrovně, když vede z karty
// zdrojového kroku do karty cílového kroku; kroky na téže kartě nebo mimo úroveň vazbu nemají. Krok „menu“ (`nav`)
// stránku nemá. Čistá logika bez Reactu.
import { FROM_NAV } from "@/project/architecture-editor/domain-map/logic/journeys";
import type { StudioLink } from "../../logic/studio-level";
import type { StudioJourney } from "../../logic/studio-status";
import { cardInLevel, type StudioTree } from "../../logic/studio-tree";

export type LevelPlace = { tree: StudioTree; focus: string | null; links: StudioLink[] };
type Hop = { from: string; to: string };

/** Karta úrovně, pod kterou leží stránka kroku; menu, neznámý krok nebo stránka mimo úroveň = null. */
export function stepCard(place: LevelPlace, journey: StudioJourney, stepId: string): string | null {
  const page = journey.stepPages.get(stepId);
  if (!page || page === FROM_NAV) return null;
  return cardInLevel(place.tree, place.focus, page);
}

/** Vazba úrovně, po které vede přechod; null, když přechod na této úrovni vazbu nemá. */
export function hopLink(place: LevelPlace, journey: StudioJourney, hop: Hop): StudioLink | null {
  const source = stepCard(place, journey, hop.from); const target = stepCard(place, journey, hop.to);
  if (!source || !target || source === target) return null;
  return place.links.find((link) => link.source === source && link.target === target) ?? null;
}

/** Vazby trasy v pořadí přechodů (každá jednou) a karty kroků na této úrovni. */
export function routeOnLevel(place: LevelPlace, journey: StudioJourney, hops: Hop[]): { links: string[]; cards: string[] } {
  const links: string[] = [];
  for (const hop of hops) {
    const link = hopLink(place, journey, hop);
    if (link && !links.includes(link.id)) links.push(link.id);
  }
  const cards = new Set<string>();
  for (const stepId of journey.stepPages.keys()) {
    const card = stepCard(place, journey, stepId);
    if (card) cards.add(card);
  }
  return { links, cards: [...cards] };
}
