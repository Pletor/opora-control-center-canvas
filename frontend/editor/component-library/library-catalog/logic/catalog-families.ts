import type { CatalogCategory, CatalogItem } from "./library-catalog";
import type { CardLayer } from "@/shared/types/logic/types";

export const CATALOG_FAMILIES: { id: string; label: string; categories: CatalogCategory[] }[] = [
  { id: "frontend", label: "Frontend", categories: ["fe-components", "fe-css", "fe-logic"] },
  { id: "backend", label: "Backend", categories: ["backend", "tenancy", "functions", "events", "storage", "notifications", "payments", "search"] },
  { id: "database", label: "Databáze", categories: ["database"] },
  { id: "infrastructure", label: "Infrastruktura", categories: ["cloud", "cache", "security", "tests", "devops", "docker", "monitoring", "analytics", "config"] },
];

/** Infrastructure is not the library source layer; do not invent a layer mapping. */
export function catalogLayer(item: CatalogItem): CardLayer | undefined {
  if (item.category.startsWith("fe-")) return "frontend";
  if (item.category === "backend" || item.category === "tenancy") return "backend";
  if (item.category === "database") return "database";
  return undefined;
}
