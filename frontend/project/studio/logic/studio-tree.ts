// Fraktální strom Studia (docs/studio.md §2): projekt → doména → stránka → sekce → komponenta (a její děti).
// Čistá logika bez Reactu. Uzel se do úrovně přiřazuje přes `parentId` a nejbližší stránku / `card.section`
// stejně jako backend `node_architecture` (`nearest_page`). Sekce nejsou uzly grafu: Studio je skládá
// z `site.sections` stránky a dává jim virtuální id `section:<stránka>:<sekce>`. Komponenta stránky se sekcemi,
// jejíž `card.section` žádnou sekci té stránky neoznačuje, leží přímo na úrovni stránky ve skupině „bez sekce“.
import type { CanvasNode, Graph, PageSection } from "@/shared/types/logic/types";

export type StudioKind = "domain" | "page" | "section" | "component";
export type StudioItem = {
  /** Id uzlu grafu, u sekce virtuální `section:<stránka>:<sekce>`. */
  id: string;
  kind: StudioKind;
  name: string;
  purpose: string;
  /** Uzel grafu; sekce žádný nemá. */
  node: CanvasNode | null;
  /** Nejbližší stránka (stránka sama, u sekce její stránka); null = mimo stránky. */
  pageId: string | null;
  /** Nejbližší doména (doména sama). */
  domainId: string | null;
  section?: PageSection;
  /** Komponenta stránky se sekcemi bez platné `card.section`: leží ve skupině „bez sekce“. */
  unsectioned?: boolean;
};
export type StudioTree = {
  items: Map<string, StudioItem>;
  /** Rodič položky ve Studiu; null = úroveň projektu. */
  parent: Map<string, string | null>;
  /** Děti v pořadí grafu (u stránky nejdřív sekce); klíč null = domény projektu. */
  children: Map<string | null, string[]>;
};

export const sectionItemId = (pageId: string, sectionId: string) => `section:${pageId}:${sectionId}`;
const isApp = (node: CanvasNode) => node.site?.kind === "application";
const isPage = (node: CanvasNode) => node.site?.kind === "page";
const sectionsOf = (node: CanvasNode): PageSection[] => (node.site?.kind === "page" ? node.site.sections ?? [] : []);

/** Předci uzlu po `parentId` (bez uzlu samého), odspodu; cyklus ani chybějící rodič nevyhodí výjimku. */
function ancestors(byId: Map<string, CanvasNode>, node: CanvasNode): CanvasNode[] {
  const chain: CanvasNode[] = [];
  const seen = new Set([node.id]);
  for (let id = node.parentId; id && !seen.has(id); ) {
    const next = byId.get(id);
    if (!next) break;
    seen.add(id); chain.push(next); id = next.parentId;
  }
  return chain;
}

/** Strukturní složky, pod kterými leží stránka (nejsou samy stránkou ani doménou): ve Studiu se přeskakují. */
function pageContainers(byId: Map<string, CanvasNode>, nodes: CanvasNode[]): Set<string> {
  const containers = new Set<string>();
  for (const node of nodes) if (isPage(node)) for (const up of ancestors(byId, node)) if (!up.site) containers.add(up.id);
  return containers;
}

export function buildStudioTree(graph: Graph): StudioTree {
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const containers = pageContainers(byId, graph.nodes);
  const included = (node: CanvasNode) => (node.kind === "node" || node.kind === "sector") && !containers.has(node.id);
  const items = new Map<string, StudioItem>();
  const parent = new Map<string, string | null>();
  const children = new Map<string | null, string[]>();
  const add = (item: StudioItem, up: string | null) => {
    items.set(item.id, item); parent.set(item.id, up);
    if (!children.has(up)) children.set(up, []);
    children.get(up)!.push(item.id);
  };
  const placed: { node: CanvasNode; up: string | null; unsectioned: boolean }[] = [];
  for (const node of graph.nodes) {
    if (!included(node)) continue;
    const chain = ancestors(byId, node).filter(included);
    const domain = (isApp(node) ? node : chain.find(isApp)) ?? null;
    if (isApp(node)) { placed.push({ node, up: chain.find(isApp)?.id ?? null, unsectioned: false }); continue; }
    if (!domain) continue; // mimo doménu Studio nic nekreslí
    if (isPage(node)) { placed.push({ node, up: chain.find((up) => isPage(up) || isApp(up))!.id, unsectioned: false }); continue; }
    const up = chain[0];
    if (!up || !isPage(up)) { placed.push({ node, up: up?.id ?? domain.id, unsectioned: false }); continue; }
    const sections = sectionsOf(up);
    const section = sections.find((item) => item.id === node.card?.section);
    placed.push({ node, up: section ? sectionItemId(up.id, section.id) : up.id, unsectioned: sections.length > 0 && !section });
  }
  const pageOf = (node: CanvasNode) => (isPage(node) ? node.id : ancestors(byId, node).find(isPage)?.id ?? null);
  const domainOf = (node: CanvasNode) => (isApp(node) ? node.id : ancestors(byId, node).find(isApp)?.id ?? null);
  for (const { node, up, unsectioned } of placed) {
    const kind: StudioKind = isApp(node) ? "domain" : isPage(node) ? "page" : "component";
    add({ id: node.id, kind, name: node.name || node.id, purpose: node.purpose, node, pageId: kind === "domain" ? null : pageOf(node), domainId: domainOf(node), ...(unsectioned ? { unsectioned } : {}) }, up);
    if (kind === "page") for (const section of sectionsOf(node)) {
      add({ id: sectionItemId(node.id, section.id), kind: "section", name: section.name || section.id, purpose: section.intent, node: null, pageId: node.id, domainId: domainOf(node), section }, node.id);
    }
  }
  // Sekce stránky stojí před ostatními dětmi stránky, aby pořadí odpovídalo stránce shora dolů.
  for (const [up, ids] of children) if (up && items.get(up)?.kind === "page") ids.sort((a, b) => Number(items.get(b)!.kind === "section") - Number(items.get(a)!.kind === "section"));
  return { items, parent, children };
}

/** Cesta od projektu k uzlu (bez projektu): pro drobečky. Neznámé id = prázdná cesta (úroveň projektu). */
export function studioTrail(tree: StudioTree, id: string | null): StudioItem[] {
  const trail: StudioItem[] = [];
  const seen = new Set<string>();
  for (let cursor = id; cursor && tree.items.has(cursor) && !seen.has(cursor); cursor = tree.parent.get(cursor) ?? null) {
    seen.add(cursor); trail.unshift(tree.items.get(cursor)!);
  }
  return trail;
}

/** Všichni potomci položky ve Studiu (bez ní samé), do hloubky. */
export function studioDescendants(tree: StudioTree, id: string | null): StudioItem[] {
  const result: StudioItem[] = [];
  const stack = [...(tree.children.get(id) ?? [])];
  const seen = new Set<string>();
  while (stack.length) {
    const next = stack.shift()!;
    if (seen.has(next)) continue;
    seen.add(next); result.push(tree.items.get(next)!);
    stack.push(...(tree.children.get(next) ?? []));
  }
  return result;
}

/** Karta úrovně `focusId`, pod kterou leží položka `id` (ona sama nebo její předek); null = mimo úroveň. */
export function cardInLevel(tree: StudioTree, focusId: string | null, id: string): string | null {
  const seen = new Set<string>();
  for (let cursor: string | null = id; cursor && tree.items.has(cursor) && !seen.has(cursor); cursor = tree.parent.get(cursor) ?? null) {
    seen.add(cursor);
    if ((tree.parent.get(cursor) ?? null) === focusId) return cursor;
  }
  return null;
}
