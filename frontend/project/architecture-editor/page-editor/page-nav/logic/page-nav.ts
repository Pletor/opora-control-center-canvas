// Pruh navigace domény nad plátnem Editoru stránky: stejné stránky, pořadí a popisky jako NAVBAR na Mapě domény
// (`domainPageTree` + `navLabelOf`), aktivní stránka = otevřený rozsah. Čistá logika bez Reactu, test vedle.
import type { ProductBranch } from "@/project/product-tree/logic/product-tree";
import { navLabelOf } from "../../../domain-map/logic/page-site";

/** Položka pruhu: `current` = otevřená stránka, `onPath` = ona nebo její předek (zvýrazní se rodič podstránky). */
export type NavItem = { id: string; label: string; current: boolean; onPath: boolean; depth: number };
/** `top` = hlavní stránky jako NAVBAR, `sub` = podstránky aktivní větve (hloubka od 1), jinak prázdné. */
export type PageNav = { top: NavItem[]; sub: NavItem[] };

function contains(branch: ProductBranch, id: string): boolean {
  return branch.node.id === id || branch.children.some((child) => contains(child, id));
}

function flatten(branches: ProductBranch[], active: string | null, depth: number): NavItem[] {
  return branches.flatMap((branch) => [item(branch, active, depth), ...flatten(branch.children, active, depth + 1)]);
}

function item(branch: ProductBranch, active: string | null, depth: number): NavItem {
  return { id: branch.node.id, label: navLabelOf(branch.node), current: branch.node.id === active,
    onPath: active !== null && contains(branch, active), depth };
}

/** Pruh navigace pro aktivní stránku `active` (nejbližší stránka otevřeného rozsahu, nebo `null`). */
export function pageNav(pages: ProductBranch[], active: string | null): PageNav {
  const top = pages.map((branch) => item(branch, active, 0));
  const branch = pages.find((candidate) => active !== null && contains(candidate, active));
  return { top, sub: branch ? flatten(branch.children, active, 1) : [] };
}
