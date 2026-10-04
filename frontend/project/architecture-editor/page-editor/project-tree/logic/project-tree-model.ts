// Strom projektu v levém panelu Editoru stránky: projekce grafu (žádné druhé úložiště).
// Domény (sektory `site.kind = "application"`) se seskupí podle svého jediného prostředí,
// starší vícehostové aplikace spadnou do „Sdílené struktury“. Pod doménou jsou její stránky
// v uloženém pořadí, podstránky s hloubkou pro odsazení. Bez Reactu, test vedle.
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { productTree, type ProductBranch } from "@/project/product-tree/logic/product-tree";
import { DOMAIN_KIND_LABEL, domainKindOf, type DomainKind } from "../../../landing/logic/domain-kind";

export type TreeTone = "live" | "dev" | "shared" | "other";
export type TreePage = { id: string; name: string; path: string | null; depth: number; active: boolean };
export type TreeDomain = {
  id: string; name: string; host: string | null; kind: DomainKind; kindLabel: string;
  purpose: string; active: boolean; pages: TreePage[];
};
export type TreeGroup = { id: string; label: string; badge: string | null; tone: TreeTone; active: boolean; domains: TreeDomain[] };

export const SHARED_GROUP = "Sdílená struktura";
const FIXED: { label: string; badge: string; tone: TreeTone }[] = [
  { label: "Produkce", badge: "LIVE", tone: "live" },
  { label: "Vývoj", badge: "DEV", tone: "dev" },
];

/** Jediné prostředí domény; vícehostová nebo prázdná aplikace žádné vlastní nemá. */
export function environmentOf(node: CanvasNode): { name: string; host: string } | null {
  return node.site?.kind === "application" && node.site.environments.length === 1 ? node.site.environments[0] : null;
}

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

function flatten(branches: ProductBranch[], activePage: string | null, depth = 0): TreePage[] {
  return branches.flatMap(({ node, children }) => node.site?.kind !== "page" ? [] : [
    { id: node.id, name: node.name, path: node.site.path || null, depth, active: node.id === activePage },
    ...flatten(children, activePage, depth + 1),
  ]);
}

function domainOf(branch: ProductBranch, activeDomain: string | null, activePage: string | null): TreeDomain {
  const node = branch.node;
  const env = environmentOf(node);
  const hosts = node.site?.kind === "application" ? node.site.environments.map((item) => item.host).filter(Boolean) : [];
  const host = env?.host || hosts.join(", ") || null;
  const kind = domainKindOf(node);
  return {
    id: node.id, name: node.name, host, kind, kindLabel: DOMAIN_KIND_LABEL[kind], purpose: node.purpose,
    active: node.id === activeDomain, pages: flatten(branch.children, activePage),
  };
}

/** Skupiny prostředí v pevném pořadí: Produkce, Vývoj, další pojmenovaná prostředí, Sdílená struktura. */
export function projectTree(graph: Graph, activeDomain: string | null, activePage: string | null): TreeGroup[] {
  const apps = productTree(graph.nodes).filter((branch) => branch.node.site?.kind === "application");
  const byGroup = new Map<string, TreeDomain[]>();
  for (const branch of apps) {
    const name = environmentOf(branch.node)?.name || SHARED_GROUP;
    byGroup.set(name, [...(byGroup.get(name) ?? []), domainOf(branch, activeDomain, activePage)]);
  }
  const others = [...byGroup.keys()].filter((name) => name !== SHARED_GROUP && !FIXED.some((fixed) => fixed.label === name));
  const order = [...FIXED, ...others.map((label) => ({ label, badge: null, tone: "other" as TreeTone })),
    ...(byGroup.has(SHARED_GROUP) ? [{ label: SHARED_GROUP, badge: null, tone: "shared" as TreeTone }] : [])];
  return order.map(({ label, badge, tone }) => {
    const domains = byGroup.get(label) ?? [];
    return { id: label, label, badge, tone, active: domains.some((domain) => domain.active), domains };
  });
}
