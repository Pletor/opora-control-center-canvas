// Paleta vrstvy Layout: druhy boxů a tři šablony (docs/navrhy/2026-11-10-platno-2.md). Šablona nahradí celý layout;
// id nových sekcí se nekříží s dosavadními, aby prvek logiky po zmizelém boxu nepadl do cizího. Bez Reactu, test vedle.
import type { PageSection, PageSectionRole } from "@/shared/types/logic/types";
import { newSectionId, type BoxKind } from "./layout-edit";
import type { LayoutSection } from "./layout-grid";

export const BOX_KINDS: BoxKind[] = [
  { role: "header", name: "Hlavička", w: 12, h: 2 },
  { role: "nav", name: "Navigace", w: 12, h: 1 },
  { role: "custom", name: "Sekce", w: 12, h: 4 },
  { role: "article", name: "Článek", w: 8, h: 6 },
  { role: "aside", name: "Boční panel", w: 4, h: 6 },
  { role: "footer", name: "Patička", w: 12, h: 2 },
  { role: "cta", name: "Výzva", w: 12, h: 3 },
  { role: "form", name: "Formulář", w: 6, h: 5 },
  { role: "gallery", name: "Galerie", w: 12, h: 4 },
  { role: "content", name: "Obsah", w: 12, h: 4 },
];

type TemplateBox = [PageSectionRole, string, number, number, number, number];
export type LayoutTemplate = { id: string; name: string; note: string; boxes: TemplateBox[] };

export const TEMPLATES: LayoutTemplate[] = [
  { id: "classic", name: "Klasický web", note: "hlavička / navigace + obsah + boční panel / patička", boxes: [
    ["header", "Hlavička", 0, 0, 12, 2], ["nav", "Navigace", 0, 2, 2, 8], ["main", "Obsah", 2, 2, 7, 8], ["aside", "Boční panel", 9, 2, 3, 8], ["footer", "Patička", 0, 10, 12, 2],
  ] },
  { id: "landing", name: "Landing", note: "hlavička / úvod / 3 sloupce / výzva / patička", boxes: [
    ["header", "Hlavička", 0, 0, 12, 2], ["hero", "Úvod", 0, 2, 12, 5], ["content", "Sloupec 1", 0, 7, 4, 4], ["content", "Sloupec 2", 4, 7, 4, 4],
    ["content", "Sloupec 3", 8, 7, 4, 4], ["cta", "Výzva", 0, 11, 12, 3], ["footer", "Patička", 0, 14, 12, 2],
  ] },
  { id: "app", name: "Aplikace", note: "hlavička / boční navigace + hlavní obsah", boxes: [
    ["header", "Hlavička", 0, 0, 12, 2], ["nav", "Boční navigace", 0, 2, 3, 12], ["main", "Hlavní obsah", 3, 2, 9, 12],
  ] },
];

/** Sekce šablony s id volnými vůči `used` (dosavadní sekce stránky); neznámá šablona = prázdný layout. */
export function templateSections(id: string, used: Pick<PageSection, "id">[]): LayoutSection[] {
  const sections: LayoutSection[] = [];
  for (const [role, name, x, y, w, h] of TEMPLATES.find((template) => template.id === id)?.boxes ?? []) {
    sections.push({ id: newSectionId([...used, ...sections]), role, name, intent: "", box: { x, y, w, h } });
  }
  return sections;
}
