// Tok domény podle druhu `carries` pro pohled Studio (docs/architektura-pro-agenty.md §3.4 a §7). Čistá logika bez Reactu:
// vazby mezi uzly domény (oba konce pod doménou, jen vazby `next`, které druh toku nést smějí) rozdělí podle druhu
// toku, uvnitř druhu seskupí podle stránky zdroje a každé položce dá cíl kliku ve tvaru nálezu kontroly mapy, aby ji
// otevřel tentýž `onOpenFinding` v ArchitectureEditor (stránka zdroje + vybraný zdrojový uzel).
import { EDGE_CARRIES, type EdgeCarries, type Graph } from "@/shared/types/logic/types";
import { CARRIES_LABEL, canCarry } from "@/shared/edge-carries/logic/edge-carries";
import { lineage, type MapCheckTarget } from "../../map-check/logic/map-check";

/** Druh toku; `unspecified` = vazba, která druh zatím nemá. */
export type FlowKind = EdgeCarries | "unspecified";
export const FLOW_KINDS: FlowKind[] = [...EDGE_CARRIES, "unspecified"];
export const FLOW_LABEL: Record<FlowKind, string> = { ...CARRIES_LABEL, unspecified: "Neurčeno" };

/** Jedna vazba „zdroj → cíl“; `target` = kam vede klik (null, když zdroj neleží pod stránkou). */
export type FlowItem = { edgeId: string; sourceId: string; sourceName: string; targetName: string; target: MapCheckTarget | null };
/** Vazby jednoho druhu se zdrojem na téže stránce; `pageId` null = zdroj mimo stránky (přímo pod doménou). */
export type FlowPageGroup = { pageId: string | null; pageName: string; items: FlowItem[] };
export type FlowSummary = { kind: FlowKind; label: string; count: number; groups: FlowPageGroup[] };

const OUTSIDE = "Mimo stránky";
const byName = (a: string, b: string) => a.localeCompare(b, "cs");

/** Souhrn toků domény `domainId` v pevném pořadí druhů (navigace, data, příkaz, událost, neurčeno), i prázdné druhy. */
export function domainFlows(graph: Graph, domainId: string): FlowSummary[] {
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const inDomain = (id: string) => lineage(byId, id).some((node) => node.id === domainId);
  const pageOf = (id: string) => lineage(byId, id).find((node) => node.site?.kind === "page");
  const name = (id: string) => byId.get(id)?.name || id;
  const kinds = new Map<FlowKind, Map<string, FlowPageGroup>>(FLOW_KINDS.map((kind) => [kind, new Map()]));
  for (const edge of graph.edges) {
    if (!canCarry(edge) || !inDomain(edge.source) || !inDomain(edge.target)) continue;
    const kind: FlowKind = edge.carries && Object.hasOwn(CARRIES_LABEL, edge.carries) ? edge.carries : "unspecified";
    const page = pageOf(edge.source);
    const target: MapCheckTarget | null = !page ? null : page.id === edge.source ? { kind: "page", id: page.id } : { kind: "node", id: edge.source, pageId: page.id };
    const groups = kinds.get(kind)!;
    const key = page?.id ?? "";
    if (!groups.has(key)) groups.set(key, { pageId: page?.id ?? null, pageName: page ? page.name || page.id : OUTSIDE, items: [] });
    groups.get(key)!.items.push({ edgeId: edge.id, sourceId: edge.source, sourceName: name(edge.source), targetName: name(edge.target), target });
  }
  return FLOW_KINDS.map((kind) => {
    const groups = [...kinds.get(kind)!.values()]
      .sort((a, b) => (a.pageId === null ? 1 : 0) - (b.pageId === null ? 1 : 0) || byName(a.pageName, b.pageName))
      .map((group) => ({ ...group, items: group.items.sort((a, b) => byName(a.sourceName, b.sourceName) || byName(a.targetName, b.targetName) || byName(a.edgeId, b.edgeId)) }));
    return { kind, label: FLOW_LABEL[kind], count: groups.reduce((sum, group) => sum + group.items.length, 0), groups };
  });
}
