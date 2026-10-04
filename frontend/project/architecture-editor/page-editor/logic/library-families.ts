// Rodiny Knihovny prvků tak, jak je ukazuje kontrakt (docs/architektura-projektu.md, krok 3):
// Frontend, Backend, Databáze, Security, Testy, Cache, Cloud a infrastruktura. Každá kategorie
// katalogu patří právě jedné rodině; barva rodiny je token vrstvy (`--ae-tone-*`).
import { searchItems, type CatalogCategory, type CatalogItem } from "@/editor/component-library/library-catalog/logic/library-catalog";
import type { Tone } from "./canvas-model";

export type LibraryFamily = { id: string; label: string; tone: Tone; categories: CatalogCategory[] };
export type IconName = "frontend" | "style" | "logic" | "backend" | "tenant" | "database" | "security" | "tests" | "cache" | "cloud";

export const LIBRARY_FAMILIES: LibraryFamily[] = [
  { id: "frontend", label: "Frontend", tone: "frontend", categories: ["fe-components", "fe-css", "fe-logic"] },
  { id: "backend", label: "Backend", tone: "backend", categories: ["backend", "tenancy"] },
  { id: "database", label: "Databáze", tone: "database", categories: ["database"] },
  { id: "security", label: "Security", tone: "security", categories: ["security"] },
  { id: "tests", label: "Testy", tone: "infrastructure", categories: ["tests"] },
  { id: "cache", label: "Cache", tone: "cache", categories: ["cache"] },
  { id: "cloud", label: "Cloud a infrastruktura", tone: "infrastructure", categories: ["cloud"] },
];

/** Ikona dlaždice podle kategorie; jen piktogram, význam nese popisek. */
export const CATEGORY_ICON: Record<CatalogCategory, IconName> = {
  "fe-components": "frontend", "fe-css": "style", "fe-logic": "logic", backend: "backend", tenancy: "tenant",
  database: "database", security: "security", tests: "tests", cache: "cache", cloud: "cloud",
};

/** Neprázdné rodiny s prvky, které odpovídají hledání, v pořadí kontraktu. */
export function libraryFamilies(items: CatalogItem[], query: string): { family: LibraryFamily; items: CatalogItem[] }[] {
  const found = searchItems(items, query);
  return LIBRARY_FAMILIES
    .map((family) => ({ family, items: found.filter((item) => family.categories.includes(item.category)) }))
    .filter((group) => group.items.length > 0);
}
