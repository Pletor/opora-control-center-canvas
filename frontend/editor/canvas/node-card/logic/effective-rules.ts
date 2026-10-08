import type { Graph } from "@/shared/types/logic/types";
import type { DesktopState, NodeRule } from "@/shared/desktop-state/logic/types";

export type EffectiveRule = NodeRule & { origin: { scope: "project" | "path" | "sector" | "card";
  nodeId: string; name: string; path: string; storage: "project" | "node" }; inherited: boolean };

export function effectiveRules(graph: Graph, state: DesktopState, nodeId: string): EffectiveRule[] {
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const lineage: string[] = [];
  let cursor: string | null = nodeId;
  while (cursor && byId.has(cursor) && !lineage.includes(cursor)) {
    lineage.push(cursor); cursor = byId.get(cursor)!.parentId;
  }
  const path = byId.get(nodeId)?.sourceRef?.path ?? "";
  const origin = (owner: string, storage: "project" | "node", scope?: EffectiveRule["origin"]["scope"], target = ""): EffectiveRule["origin"] => ({
    scope: scope ?? (byId.get(owner)?.kind === "sector" ? "sector" : "card"),
    nodeId: owner, name: byId.get(owner)?.name ?? "", path: target, storage,
  });
  const rows: EffectiveRule[] = [];
  for (const rule of state.rules) {
    let source: EffectiveRule["origin"];
    if (rule.scope === "project") source = origin("", "project", "project");
    else if (rule.scope === "path" && path && (path === rule.target || path.startsWith(rule.target + "/"))) source = origin("", "project", "path", rule.target);
    else if (rule.scope === "node" && lineage.includes(rule.target)) source = origin(rule.target, "project");
    else continue;
    rows.push({ ...rule, origin: source, inherited: source.nodeId !== nodeId });
  }
  for (const owner of [...lineage].reverse()) for (const rule of state.nodes[owner]?.rules ?? []) {
    rows.push({ ...rule, origin: origin(owner, "node"), inherited: owner !== nodeId });
  }
  return rows;
}
