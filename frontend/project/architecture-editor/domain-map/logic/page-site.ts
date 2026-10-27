// Záměr stránky pro člověka (cíl, působení, popisek v menu) a sekce od agenta; čistá logika bez Reactu.
// Kontrakt: docs/architektura-pro-agenty.md §3.1. Prázdné pole se neukládá, výchozí hodnota se nikdy nedoplní.
import type { CanvasNode, PageSectionRole, PageSite } from "@/shared/types/logic/types";
import { normalizePagePath } from "@/project/product-tree/logic/page-path";

/** Pole, která na stránce vyplňuje člověk, s horní mezí délky podle backendu (`site_metadata.py`). */
export const PAGE_INTENT_FIELDS = [
  { key: "goal", label: "Cíl stránky", max: 200, placeholder: "Poptávka odeslaná do 2 minut" },
  { key: "feel", label: "Působení", max: 120, placeholder: "klidně, důvěryhodně" },
  { key: "navLabel", label: "Popisek v menu", max: 40, placeholder: "Kontakt" },
] as const;
export type PageIntentKey = (typeof PAGE_INTENT_FIELDS)[number]["key"];

export const SECTION_ROLE_LABELS: Record<PageSectionRole, string> = {
  hero: "Úvod", cta: "Výzva", form: "Formulář", content: "Obsah", gallery: "Galerie",
  proof: "Důkaz", faq: "Otázky", footer: "Patička", custom: "Vlastní",
};

/** Upraví jedno pole záměru a zachová zbytek `site` (sekce, ostatní pole). */
export function withPageIntent(site: PageSite, key: PageIntentKey, value: string): PageSite {
  return { ...site, [key]: value };
}

/** Před uložením: cesta v normálním tvaru, text oříznutý a prázdné pole vynechané; sekce beze změny. */
export function pageSiteForSave(site: PageSite): PageSite {
  const result: PageSite = { ...site, path: normalizePagePath(site.path) };
  for (const { key } of PAGE_INTENT_FIELDS) {
    const value = site[key]?.trim();
    if (value) result[key] = value;
    else delete result[key];
  }
  return result;
}

/** Text tlačítka v navigaci: popisek v menu, když ho člověk nastavil, jinak název stránky. */
export function navLabelOf(node: Pick<CanvasNode, "name" | "site">): string {
  return (node.site?.kind === "page" ? node.site.navLabel : undefined) ?? node.name;
}
