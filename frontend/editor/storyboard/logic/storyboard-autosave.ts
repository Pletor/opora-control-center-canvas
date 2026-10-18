// Rozhodování automatického ukládání storyboardu bez Reactu: kdy uložit koncept, co udělat při odchodu z karty
// a kdy prohlížeč varuje před zavřením. Stejný rytmus jako text karty (700 ms po poslední změně).
import type { StoryboardStatus } from "./use-storyboard-store";

export const AUTOSAVE_MS = 700;

/** Co hook ví o konceptu v jednu chvíli. */
export type SaveGate = {
  /** Koncept existuje a liší se od uložené podoby. */
  dirty: boolean;
  /** Koncept prošel `validate`; chybný se neukládá. */
  valid: boolean;
  /** Karta je jen ke čtení (aplikace nebo server). */
  readOnly: boolean;
  status: StoryboardStatus;
};

const savable = (g: SaveGate) => g.dirty && g.valid && !g.readOnly;

/**
 * Za kolik ms se má koncept uložit, nebo null (neukládat). `pending` = během běžícího ukládání přišla další změna,
 * takže se uloží hned po dokončení. `sameAsFailed` = koncept je přesně ten, jehož uložení právě selhalo;
 * znovu se zkusí až po další změně (jinak by se chyba opakovala dokola).
 */
export function autosaveDelay(g: SaveGate, pending: boolean, sameAsFailed: boolean): number | null {
  if (!savable(g)) return null;
  if (g.status === "saving" || g.status === "conflict" || g.status === "loading") return null;
  if (g.status === "error" && sameAsFailed) return null;
  return pending ? 0 : AUTOSAVE_MS;
}

/** Při odchodu z karty (přepnutí karty nebo módu, zavření stránky): uložit neuložený platný koncept? */
export function saveOnLeave(g: SaveGate): boolean {
  // Při běžícím ukládání by druhý zápis šel se starou revizí (409); při konfliktu a načítání se neukládá vůbec.
  return savable(g) && (g.status === "idle" || g.status === "error");
}

/** Varovat před zavřením stránky? Jen když se koncept uložit nedá: selhalo to, je v konfliktu nebo je chybný. */
export function warnOnUnload(g: SaveGate): boolean {
  if (!g.dirty || g.readOnly) return false;
  return g.status === "error" || g.status === "conflict" || !g.valid;
}
