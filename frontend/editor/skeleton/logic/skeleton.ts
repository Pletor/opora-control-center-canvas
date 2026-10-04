import type { CanvasNode, Graph } from "@/shared/types/logic/types";

/** Kostra is a view of the design graph. Source paths and code are never created here. */
export const STARTER_SECTORS = ["Frontend", "Backend", "Databáze", "Integrace", "Provoz", "Ověření"];
export const structureNodes = (nodes: CanvasNode[]) => nodes.filter((node) => node.kind === "sector" || node.kind === "node");

export function appendSkeleton(graph: Graph, parentId: string | null, names: string[], kind: "node" | "sector", id: () => string): Graph {
  const parent = graph.nodes.find((node) => node.id === parentId);
  if (parentId !== null && (!parent || (parent.kind !== "node" && parent.kind !== "sector"))) throw new Error("Vyberte existující část Kostry.");
  const siblings = graph.nodes.filter((node) => node.parentId === parentId);
  const seen = new Set(structureNodes(siblings).map((node) => node.name.trim().toLocaleLowerCase("cs")));
  const added: CanvasNode[] = [];
  let y = siblings.length ? Math.max(...siblings.map((node) => node.y + (node.size?.h ?? 360))) + 80 : 80;
  for (const raw of names) {
    const name = raw.trim();
    if (!name || seen.has(name.toLocaleLowerCase("cs"))) continue;
    if (name.length > 160) throw new Error("Název části smí mít nejvýše 160 znaků.");
    seen.add(name.toLocaleLowerCase("cs"));
    added.push({ id: id(), parentId, kind, name, purpose: "", x: 80, y });
    y += 440;
  }
  return added.length ? { ...graph, nodes: [...graph.nodes, ...added] } : graph;
}

/** Ancestors open the selected branch without copying the nodes into another tree. */
export function ancestorIds(nodes: CanvasNode[], selected: string | null): string[] {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const result: string[] = [];
  const seen = new Set<string>();
  let node = selected ? byId.get(selected) : undefined;
  while (node?.parentId && !seen.has(node.parentId)) {
    seen.add(node.parentId);
    result.push(node.parentId);
    node = byId.get(node.parentId);
  }
  return result;
}
