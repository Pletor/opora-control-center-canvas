// Rozepsaná karta uzlu (docs/kontext-karet-a-index.md §1): vrstva a pole „Pro agenta“ jako obyčejné
// řetězce, prázdný = nevyplněno. Sdílí ji pop-up tvorby i detail karty; při uložení se prázdné klíče
// vypustí (`normalizeCard` ze `shared/card-context`). Bez Reactu, s testem `card-draft.test.ts`.
import type { CardLayer, NodeCardFields } from "@/shared/types/logic/types";

/** Rozepsaná karta: prázdný řetězec = nevyplněno; při vytvoření se prázdné klíče vypustí. */
export type CardDraft = Record<keyof NodeCardFields, string>;

export const emptyCard = (): CardDraft => ({ layer: "", status: "", due: "", model: "", effort: "" });

/** Uložená karta jako rozepsaná: chybějící klíč je prázdný řetězec (detail karty z ní začíná). */
/** Bere jen pole formuláře; technologii a stavy komponenty píše agent a formulář je nenese. */
export const cardDraftOf = (card: NodeCardFields | undefined): CardDraft => {
  const draft = emptyCard();
  for (const key of Object.keys(draft) as (keyof CardDraft)[]) draft[key] = card?.[key] ?? "";
  return draft;
};

/** Zda dvě rozepsané karty říkají totéž; detail karty podle toho ukáže tlačítko Uložit. */
export const sameCardDraft = (a: CardDraft, b: CardDraft): boolean =>
  (Object.keys(a) as (keyof CardDraft)[]).every((key) => a[key] === b[key]);

/** Klik na čip vrstvy: vybere ji, druhý klik na tutéž výběr zruší (vrstva je nepovinná). */
export const toggleLayer = (card: CardDraft, layer: CardLayer): CardDraft => ({ ...card, layer: card.layer === layer ? "" : layer });

/**
 * Souhrn sbalené sekce „Pro agenta“: jen vyplněné hodnoty, např. `ready · sonnet/medium · 2026-10-10`.
 * Model a effort tvoří jednu dvojici, protože se vybírají spolu. Nic vyplněné = prázdný řetězec.
 */
export function agentSummary(card: CardDraft): string {
  const pair = [card.model, card.effort].filter(Boolean).join("/");
  return [card.status, pair, card.due].filter(Boolean).join(" · ");
}
