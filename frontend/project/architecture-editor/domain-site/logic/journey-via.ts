// Signál přechodu do kroku cesty (`via`): co zákazník udělá na stránce předchozího kroku, aby se dostal sem.
// Čistá logika bez Reactu. Kontrakt: docs/architektura-pro-agenty.md §3.2, návrh docs/cesta-zakaznika-a-brief.md §3.
// Sekce se tu jen čte: odkaz na sekci, kterou stránka nemá, se ukládá dál a ohlásí ho kontrola mapy (`journey.via-unknown`).
import type { CanvasNode, JourneyAction, JourneyVia, PageSection } from "@/shared/types/logic/types";

/** Nejvýš tolik znaků smí mít viditelný text prvku (`via.text`), stejně jako backend (`site_metadata.py`). */
export const VIA_TEXT_MAX = 60;

/** Akce, které krok smí mít: první krok jen otevření stránky, další jen klik nebo odeslání na předchozí stránce. */
export function viaActions(index: number): { value: JourneyAction; label: string }[] {
  return index === 0 ? [{ value: "open", label: "Otevře stránku přímo" }]
    : [{ value: "click", label: "Klikne na odkaz nebo tlačítko" }, { value: "submit", label: "Odešle formulář" }];
}

/** Signál, který krok na pozici `index` smí nést: první krok jen `{do: open}`, další ne `open`; jinak signál zmizí. */
export function fitVia(index: number, via: JourneyVia | undefined): JourneyVia | undefined {
  if (!via) return undefined;
  if (index === 0) return via.do === "open" ? { do: "open" } : undefined;
  return via.do === "open" ? undefined : via;
}

/** Před uložením: oříznutý text, prázdná sekce a text se vynechají, nic se nedoplňuje. */
export function viaForSave(via: JourneyVia): JourneyVia {
  const section = via.section?.trim(), text = via.text?.trim();
  return { do: via.do, ...(section ? { section } : {}), ...(text ? { text } : {}) };
}

/** Sekce stránky `pageId` (z jejího `site.sections`); menu a chybějící stránka sekce nemají. */
export function sectionsOfPage(pageId: string | null, pages: Pick<CanvasNode, "id" | "site">[]): PageSection[] {
  const site = pages.find((page) => page.id === pageId)?.site;
  return site?.kind === "page" ? site.sections ?? [] : [];
}

/** Čitelná věta signálu: „odešle formulář „Odeslat“ v sekci Výzva“. `missingSection` = id sekce, kterou předchozí
 * stránka nemá (věta ji pak jmenuje jen id). */
export function viaSentence(via: JourneyVia, sections: PageSection[]): { text: string; missingSection: string | null } {
  if (via.do === "open") return { text: "otevře stránku přímo", missingSection: null };
  const section = via.section ? sections.find((item) => item.id === via.section) : undefined;
  const quoted = via.text ? `„${via.text}“` : "";
  const action = via.do === "submit" ? "odešle formulář" + (quoted ? " " + quoted : "") : "klikne" + (quoted ? " na " + quoted : "");
  const where = via.section ? ` v sekci ${section?.name ?? via.section}` : "";
  return { text: action + where, missingSection: via.section && !section ? via.section : null };
}
