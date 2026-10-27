// Čistý model „Pracovního kontextu agenta“ a vazeb prvku v Detailu prvku. Vše se čte z grafu;
// co v grafu není, vrací `null` a komponenta to ukáže jako „nedostupné“.
import type { CanvasNode, Graph, GraphEdgePort } from "@/shared/types/logic/types";

export type RepoPath = { kind: "existing"; path: string } | { kind: "planned"; path: string };
export type AgentContext = {
  /** `null` = doména bez prostředí (sdílená struktura). */
  environment: string | null;
  host: string | null;
  /** Stránka s cílem a působením, jak je zadal člověk; chybějící pole se nedoplňuje. */
  page: { id: string; name: string; goal?: string; feel?: string } | null;
  /** Názvy od prvního prvku pod stránkou (nebo doménou) po vybraný prvek. */
  componentPath: string[];
  repo: RepoPath | null;
};
export type NodeLink = { edgeId: string; otherId: string; otherName: string; port: GraphEdgePort };
export const PLANNED_NOTICE = "Kontext je návrh; skutečné cesty vyžadují napojení repozitáře.";

/** Prvek a jeho předci od nejbližšího; cyklus rodičů zastaví průchod. */
export function ancestry(graph: Graph, nodeId: string): CanvasNode[] {
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const out: CanvasNode[] = [];
  const seen = new Set<string>();
  for (let cursor: string | null = nodeId; cursor && !seen.has(cursor); ) {
    seen.add(cursor);
    const node = byId.get(cursor);
    if (!node) break;
    out.push(node);
    cursor = node.parentId;
  }
  return out;
}

const label = (node: CanvasNode) => node.name.trim() || "Bez názvu";

export function agentContext(graph: Graph, nodeId: string, domainId: string): AgentContext {
  const domain = graph.nodes.find((node) => node.id === domainId);
  const env = domain?.site?.kind === "application" ? domain.site.environments[0] : undefined;
  const chain = ancestry(graph, nodeId);
  const pageIndex = chain.findIndex((node) => node.site?.kind === "page");
  const domainIndex = chain.findIndex((node) => node.id === domainId);
  const boundary = pageIndex >= 0 ? pageIndex : domainIndex;
  const below = boundary >= 0 ? chain.slice(0, boundary) : chain;
  const node = chain[0];
  const ref = node?.sourceRef;
  const pageNode = pageIndex >= 0 ? chain[pageIndex] : null;
  const pageSite = pageNode?.site?.kind === "page" ? pageNode.site : null;
  const repo: RepoPath | null = ref?.path.trim()
    ? { kind: ref.origin === "planned" ? "planned" : "existing", path: ref.path }
    : null;
  return {
    environment: env?.name.trim() || null,
    host: env?.host.trim() || domain?.name.trim() || null,
    page: pageNode ? {
      id: pageNode.id, name: label(pageNode),
      ...(pageSite?.goal ? { goal: pageSite.goal } : {}),
      ...(pageSite?.feel ? { feel: pageSite.feel } : {}),
    } : null,
    componentPath: below.reverse().map(label),
    repo,
  };
}

/** Příchozí a odchozí vazby prvku s názvem druhého konce; smyčka na sebe se počítá do obou. */
export function nodeLinks(graph: Graph, nodeId: string): { incoming: NodeLink[]; outgoing: NodeLink[] } {
  const names = new Map(graph.nodes.map((node) => [node.id, label(node)]));
  const link = (edgeId: string, otherId: string, port: GraphEdgePort | undefined): NodeLink => ({
    edgeId,
    otherId,
    otherName: names.get(otherId) ?? "nedostupné",
    port: port ?? "next",
  });
  return {
    incoming: graph.edges.filter((edge) => edge.target === nodeId).map((edge) => link(edge.id, edge.source, edge.port)),
    outgoing: graph.edges.filter((edge) => edge.source === nodeId).map((edge) => link(edge.id, edge.target, edge.port)),
  };
}
