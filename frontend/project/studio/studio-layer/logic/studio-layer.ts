// Vrstva Studia (docs/studio.md §1): Skutečnost (výchozí, jen čte) nebo MODEL (technický model domény). Volba žije
// v adrese (`studioLayer=model`); MODEL je k dispozici jen v doméně a pod ní a ukazuje model té domény. Karty OPORY,
// na které smí technická karta modelu ukázat (`binding.nodeId`), i s jejich skutečným stavem. Čistá logika bez Reactu.
import type { StudioTree } from "../../logic/studio-tree";
import { cardStatus, type StudioFacts, type StudioState } from "../../logic/studio-status";
import { KIND_LABEL, STATE_LABEL } from "../../studio-card/logic/card-view";

export type StudioLayer = "reality" | "model";
export const STUDIO_LAYER_PARAM = "studioLayer";

export function readStudioLayer(route: URLSearchParams): StudioLayer {
  return route.get(STUDIO_LAYER_PARAM) === "model" ? "model" : "reality";
}

/** Adresa po změně vrstvy; Skutečnost je výchozí, proto parametr zmizí. Ostatní parametry zůstanou. */
export function withStudioLayer(route: URLSearchParams, layer: StudioLayer): URLSearchParams {
  const next = new URLSearchParams(route);
  if (layer === "model") next.set(STUDIO_LAYER_PARAM, "model"); else next.delete(STUDIO_LAYER_PARAM);
  return next;
}

/** Doména, jejíž model se v MODELu ukáže: doména zanoření nebo jeho předka. Úroveň projektu žádnou nemá. */
export function modelDomainOf(tree: StudioTree, focus: string | null): string | null {
  return focus ? tree.items.get(focus)?.domainId ?? null : null;
}

/** MODEL bez domény neexistuje: na úrovni projektu se ukáže Skutečnost. */
export function effectiveLayer(wanted: StudioLayer, domain: string | null): StudioLayer {
  return wanted === "model" && domain ? "model" : "reality";
}

export type BindingCard = { id: string; name: string; kindLabel: string; state: StudioState; stateLabel: string };

/** Karty OPORY domény, na které se smí technická karta vázat: stránky a komponenty (sekce nejsou uzly grafu),
 * se stavem ze Skutečnosti, v pořadí stromu. */
export function bindingCards(tree: StudioTree, facts: StudioFacts, domainId: string): BindingCard[] {
  const cards: BindingCard[] = [];
  const walk = (id: string) => {
    const item = tree.items.get(id);
    if (!item) return;
    if (item.node && (item.kind === "page" || item.kind === "component")) {
      const state = cardStatus(tree, item, facts).state;
      cards.push({ id: item.id, name: item.name, kindLabel: KIND_LABEL[item.kind], state, stateLabel: STATE_LABEL[state] });
    }
    for (const child of tree.children.get(id) ?? []) walk(child);
  };
  for (const child of tree.children.get(domainId) ?? []) walk(child);
  return cards;
}
