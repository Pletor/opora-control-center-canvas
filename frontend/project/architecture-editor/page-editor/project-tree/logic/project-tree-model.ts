// Struktura v levém panelu plátna 2: projekce grafu (žádné druhé úložiště). Jen otevřená doména a její stránky
// v uloženém pořadí, podstránky s hloubkou pro odsazení a s vědomím, jestli jdou posunout mezi sourozenci. Bez Reactu, test vedle.
import type { CanvasNode, Graph, SiteEnvironment } from "@/shared/types/logic/types";
import type { ProductBranch } from "@/project/product-tree/logic/product-tree";

export type TreePage = { node: CanvasNode; path: string | null; depth: number; active: boolean; first: boolean; last: boolean };

export const SHARED_GROUP = "Sdílená struktura";

/** Jediné prostředí domény; vícehostová nebo prázdná aplikace žádné vlastní nemá. */
export function environmentOf(node: CanvasNode): SiteEnvironment | null {
  return node.site?.kind === "application" && node.site.environments.length === 1 ? node.site.environments[0] : null;
}

/** Starší sdílená struktura: aplikace s víc hosty. Plátno 2 ji neotevře, nabídne oddělení hostu na přehledu. */
export const isSharedDomain = (node: CanvasNode): boolean => node.site?.kind === "application" && node.site.environments.length > 1;

/** Nejbližší stránka nad otevřeným rozsahem (nebo rozsah sám); `null`, když žádná není. */
export function activePageId(graph: Graph, scopeId: string | null): string | null {
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const seen = new Set<string>();
  for (let cursor = scopeId; cursor && !seen.has(cursor); ) {
    seen.add(cursor);
    const node = byId.get(cursor);
    if (!node) return null;
    if (node.site?.kind === "page") return node.id;
    if (node.site?.kind === "application") return null;
    cursor = node.parentId;
  }
  return null;
}

/** Stránky domény (`domainPageTree`) jako řádky stromu: hloubka, aktivní stránka a první/poslední mezi sourozenci (↑ ↓). */
export function structureRows(pages: ProductBranch[], activePage: string | null, depth = 0): TreePage[] {
  const own = pages.filter((branch) => branch.node.site?.kind === "page");
  return own.flatMap(({ node, children }, index) => node.site?.kind !== "page" ? [] : [
    { node, path: node.site.path || null, depth, active: node.id === activePage, first: index === 0, last: index === own.length - 1 },
    ...structureRows(children, activePage, depth + 1),
  ]);
}
