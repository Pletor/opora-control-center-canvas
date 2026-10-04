import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { productTree, type ProductBranch } from "@/project/product-tree/logic/product-tree";

export type DomainEnvironment = "Produkce" | "Vývoj";

export function domainNode(graph: Graph, domainId: string): CanvasNode {
  const node = graph.nodes.find((item) => item.id === domainId);
  if (!node || node.kind !== "sector" || node.site?.kind !== "application") throw new Error("Doména v tomto projektu neexistuje.");
  return node;
}

/** The nearest application is the boundary even when applications are nested. */
export function domainForNode(graph: Graph, nodeId: string): CanvasNode | null {
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const seen = new Set<string>();
  let cursor: string | null = nodeId;
  while (cursor !== null) {
    if (seen.has(cursor)) throw new Error("Strom projektu obsahuje cyklus.");
    seen.add(cursor);
    const node = byId.get(cursor);
    if (!node) throw new Error("Část projektu již neexistuje.");
    if (node.site?.kind === "application") return domainNode(graph, node.id);
    cursor = node.parentId;
  }
  return null;
}

export function domainPageTree(graph: Graph, domainId: string): ProductBranch[] {
  domainNode(graph, domainId);
  return productTree(graph.nodes).find((branch) => branch.node.id === domainId)?.children ?? [];
}

/** Explicitly detach one legacy host; existing pages, instructions and IDs stay put. */
export function splitDomainHost(graph: Graph, appId: string, host: string, newId: string): Graph {
  const app = domainNode(graph, appId);
  if (app.site?.kind !== "application") throw new Error("Neplatná doména.");
  if (!/^[A-Za-z0-9_-]{1,80}$/.test(newId) || graph.nodes.some((node) => node.id === newId)) throw new Error("Nová doména vyžaduje vlastní nepoužité ID.");
  const environments = app.site.environments;
  const selected = environments.find((environment) => environment.host === host);
  if (environments.length < 2 || !selected) throw new Error("Oddělit lze pouze uložený host ze skupiny více domén.");
  const detached: CanvasNode = {
    id: newId, parentId: app.parentId, kind: "sector", name: selected.host, purpose: "",
    x: app.x <= 999_600 ? app.x + 400 : app.x - 400, y: app.y,
    site: { kind: "application", environments: [{ ...selected }] },
  };
  return { ...graph, nodes: [...graph.nodes.map((node) => node.id === appId
    ? { ...node, site: { kind: "application" as const, environments: environments.filter((environment) => environment !== selected) } }
    : node), detached] };
}

function pageInDomain(graph: Graph, domainId: string, pageId: string): CanvasNode {
  domainNode(graph, domainId);
  const page = graph.nodes.find((node) => node.id === pageId);
  if (!page || page.kind !== "node" || page.site?.kind !== "page" || domainForNode(graph, pageId)?.id !== domainId) throw new Error("Stránka nepatří do této domény.");
  return page;
}

export function reparentDomainPage(graph: Graph, domainId: string, pageId: string, parentId: string): Graph {
  const page = pageInDomain(graph, domainId, pageId);
  if (parentId !== domainId) pageInDomain(graph, domainId, parentId);
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const seen = new Set<string>();
  let cursor: string | null = parentId;
  while (cursor !== null) {
    if (cursor === pageId || seen.has(cursor)) throw new Error("Stránku nelze přesunout pod sebe ani svého potomka.");
    seen.add(cursor);
    cursor = byId.get(cursor)?.parentId ?? null;
  }
  if (page.parentId === parentId) return graph;
  return { ...graph, nodes: graph.nodes.map((node) => node.id === pageId ? { ...node, parentId } : node) };
}

/** Navigation siblings may have ordinary structural containers between their pages. */
export function reorderDomainPage(graph: Graph, domainId: string, pageId: string, direction: -1 | 1): Graph {
  pageInDomain(graph, domainId, pageId);
  if (direction !== -1 && direction !== 1) throw new Error("Neplatný směr změny pořadí.");
  function siblings(branches: ProductBranch[]): ProductBranch[] | null {
    if (branches.some((branch) => branch.node.id === pageId)) return branches;
    for (const branch of branches) { const found = siblings(branch.children); if (found) return found; }
    return null;
  }
  const group = siblings(domainPageTree(graph, domainId));
  if (!group) throw new Error("Stránka v mapě domény chybí.");
  const index = group.findIndex((branch) => branch.node.id === pageId);
  const neighbor = group[index + direction];
  if (!neighbor) return graph;
  const nodes = [...graph.nodes];
  const from = nodes.findIndex((node) => node.id === pageId);
  const to = nodes.findIndex((node) => node.id === neighbor.node.id);
  [nodes[from], nodes[to]] = [nodes[to], nodes[from]];
  return { ...graph, nodes };
}
