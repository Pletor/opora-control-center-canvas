// Jedna úroveň Studia (docs/studio.md §2): karty = děti otevřeného uzlu, vazby = hrany grafu mezi nimi. Hrana, která
// vede hlouběji (mezi potomky dvou různých karet), se na této úrovni sečte do jedné souhrnné vazby mezi předky; nese
// počet hran a převládající `carries`. Čistá logika bez Reactu; vazby nesou jen hrany `next` (`canCarry`), stejně
// jako druh toku na plátně Editoru stránky.
import { EDGE_CARRIES, type CanvasNode, type EdgeCarries, type Graph } from "@/shared/types/logic/types";
import { canCarry } from "@/shared/edge-carries/logic/edge-carries";
import { cardInLevel, type StudioItem, type StudioTree } from "./studio-tree";

/** Druh toku souhrnné vazby; `unspecified` = žádná z hran druh nemá. */
export type StudioFlow = EdgeCarries | "unspecified";
export const STUDIO_FLOWS: StudioFlow[] = [...EDGE_CARRIES, "unspecified"];
export type StudioLink = {
  id: string; source: string; target: string;
  /** Kolik hran grafu vazba shrnuje. */
  count: number;
  /** Převládající druh toku; při shodě vyhrává dřívější v pořadí navigace, data, příkaz, událost. */
  carries: StudioFlow;
  kinds: Partial<Record<StudioFlow, number>>;
  edgeIds: string[];
};
export type StudioLevel = { focus: StudioItem | null; cards: StudioItem[]; links: StudioLink[] };

/** Položka Studia pro uzel grafu: uzel sám, jinak nejbližší předek ve stromu (oblast, komentář, složka). */
export function itemForNode(tree: StudioTree, byId: Map<string, CanvasNode>, nodeId: string): string | null {
  const seen = new Set<string>();
  for (let cursor: string | null = nodeId; cursor && !seen.has(cursor); cursor = byId.get(cursor)?.parentId ?? null) {
    seen.add(cursor);
    if (tree.items.has(cursor)) return cursor;
  }
  return null;
}

/** Převládající druh: nejvíc hran; neurčené vyhrají, jen když žádná hrana druh nemá. */
export function dominantFlow(kinds: Partial<Record<StudioFlow, number>>): StudioFlow {
  let best: StudioFlow = "unspecified"; let most = 0;
  for (const kind of EDGE_CARRIES) if ((kinds[kind] ?? 0) > most) { best = kind; most = kinds[kind]!; }
  return best;
}

export function levelOf(tree: StudioTree, graph: Graph, focusId: string | null): StudioLevel {
  const focus = focusId ? tree.items.get(focusId) ?? null : null;
  const level = focus ? focus.id : null;
  const cards = (tree.children.get(level) ?? []).map((id) => tree.items.get(id)!);
  const links = new Map<string, StudioLink>();
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  for (const edge of graph.edges) {
    if (!canCarry(edge)) continue;
    const from = itemForNode(tree, byId, edge.source); const to = itemForNode(tree, byId, edge.target);
    const source = from && cardInLevel(tree, level, from); const target = to && cardInLevel(tree, level, to);
    if (!source || !target || source === target) continue;
    const id = `${source}->${target}`;
    const link = links.get(id) ?? { id, source, target, count: 0, carries: "unspecified", kinds: {}, edgeIds: [] };
    const kind: StudioFlow = edge.carries && (EDGE_CARRIES as string[]).includes(edge.carries) ? edge.carries : "unspecified";
    link.count += 1; link.kinds[kind] = (link.kinds[kind] ?? 0) + 1; link.edgeIds.push(edge.id);
    links.set(id, link);
  }
  return { focus, cards, links: [...links.values()].map((link) => ({ ...link, carries: dominantFlow(link.kinds) })) };
}
