// Záměr stránky pro člověka (cíl, působení, popisek v menu) a sekce od agenta; čistá logika bez Reactu.
// Kontrakt: docs/architektura-pro-agenty.md §3.1. Prázdné pole se neukládá, výchozí hodnota se nikdy nedoplní.
import type { CanvasNode, PageSection, PageSectionRole, PageSite, SectionInspiration } from "@/shared/types/logic/types";
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
  header: "Hlavička", nav: "Navigace", aside: "Boční panel", article: "Článek", main: "Hlavní obsah",
};

/** Nejvýš tolik sekcí na stránce povolí backend. */
export const MAX_PAGE_SECTIONS = 40;
/** Nejvýš tolik znaků smí mít „Čím posouvá“ (`moves`) sekce (`site_metadata.py`). */
export const SECTION_MOVES_MAX = 120;

/** Vrátí `site` s novým seznamem sekcí; prázdný seznam klíč `sections` úplně vynechá (backend prázdné pole odmítne). */
function withSections(site: PageSite, sections: PageSection[]): PageSite {
  const { sections: _old, ...rest } = site;
  return sections.length ? { ...rest, sections } : rest;
}

/** Přidá na konec novou sekci „Obsah“ s volným id `sekce-N`; na 40 sekcích nic neudělá. */
export function addSection(site: PageSite): PageSite {
  const sections = site.sections ?? [];
  if (sections.length >= MAX_PAGE_SECTIONS) return site;
  const used = new Set(sections.map((section) => section.id));
  let n = 1;
  while (used.has("sekce-" + n)) n += 1;
  return withSections(site, [...sections, { id: "sekce-" + n, role: "content", name: "Nová sekce", intent: "" }]);
}

/** Změní roli, název, záměr nebo „čím posouvá“ (`moves`) sekce podle id; samo `id` se přepsat nedá. */
export function updateSection(site: PageSite, id: string, patch: Partial<Omit<PageSection, "id">>): PageSite {
  if (!site.sections) return site;
  return withSections(site, site.sections.map((section) => (section.id === id ? { ...section, ...patch, id } : section)));
}

/** Odebere sekci podle id; po odebrání poslední zmizí i klíč `sections`. */
export function removeSection(site: PageSite, id: string): PageSite {
  if (!site.sections) return site;
  return withSections(site, site.sections.filter((section) => section.id !== id));
}

/** Posune sekci o `delta` míst (−1 nahoru, +1 dolů); na kraji seznamu zůstane, kde je. */
export function moveSection(site: PageSite, id: string, delta: number): PageSite {
  const sections = site.sections;
  const from = sections?.findIndex((section) => section.id === id) ?? -1;
  if (!sections || from < 0) return site;
  const to = Math.min(sections.length - 1, Math.max(0, from + delta));
  if (to === from) return site;
  const next = [...sections];
  next.splice(to, 0, next.splice(from, 1)[0]);
  return withSections(site, next);
}

/** Upraví jedno pole záměru a zachová zbytek `site` (sekce, ostatní pole). */
export function withPageIntent(site: PageSite, key: PageIntentKey, value: string): PageSite {
  return { ...site, [key]: value };
}

/** Před uložením: cesta v normálním tvaru, text (i název, záměr a `moves` sekcí) oříznutý a prázdné pole vynechané; bez sekcí klíč `sections` zmizí. Prázdný název sekce hlídá formulář (`required`). */
export function pageSiteForSave(site: PageSite): PageSite {
  const result: PageSite = { ...site, path: normalizePagePath(site.path) };
  for (const { key } of PAGE_INTENT_FIELDS) {
    const value = site[key]?.trim();
    if (value) result[key] = value;
    else delete result[key];
  }
  const sections = site.sections ?? [];
  const ids = new Set(sections.map((section) => section.id));
  return withSections(result, sections.map((section) => sectionForSave(section, ids)));
}

/** Sekce před uložením: název a záměr oříznuté, `moves` oříznuté a prázdné vynechané (backend prázdné odmítne).
 * `look` oříznutý a prázdný vynechaný; `box`, `status` a `source` zůstávají; `parent` na sekci, která už na stránce není (odebraná v seznamu sekcí), zmizí,
 * aby ho backend neodmítl; `inspiration` bez obsahu zmizí celá (`inspirationForSave`). */
function sectionForSave({ moves, parent, inspiration, look, ...section }: PageSection, ids: ReadonlySet<string>): PageSection {
  const trimmed = moves?.trim(), shown = look?.trim();
  const kept = inspiration && inspirationForSave(inspiration);
  return { ...section, name: section.name.trim(), intent: section.intent.trim(), ...(trimmed ? { moves: trimmed } : {}), ...(parent && ids.has(parent) ? { parent } : {}),
    ...(kept ? { inspiration: kept } : {}), ...(shown ? { look: shown } : {}) };
}

/** Inspirace boxu před uložením: odkaz a poznámka oříznuté, prázdná pole vynechaná; bez obsahu `undefined`. */
export function inspirationForSave({ files, url, note }: SectionInspiration): SectionInspiration | undefined {
  const result: SectionInspiration = {};
  if (files?.length) result.files = files;
  if (url?.trim()) result.url = url.trim();
  if (note?.trim()) result.note = note.trim();
  return Object.keys(result).length ? result : undefined;
}

/** Text tlačítka v navigaci: popisek v menu, když ho člověk nastavil, jinak název stránky. */
export function navLabelOf(node: Pick<CanvasNode, "name" | "site">): string {
  return (node.site?.kind === "page" ? node.site.navLabel : undefined) ?? node.name;
}
