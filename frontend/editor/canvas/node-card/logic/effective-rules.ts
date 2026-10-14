import type { Graph } from "@/shared/types/logic/types";
import type { DesktopState, NodeRule, Rule } from "@/shared/desktop-state/logic/types";
import type { BoardIndex } from "@/editor/canvas/board/logic/board-index";

export type EffectiveRule = NodeRule & { origin: { scope: "project" | "path" | "sector" | "card";
  nodeId: string; name: string; path: string; storage: "project" | "node" }; inherited: boolean };

/** Platná pravidla karty: projekt, cesta, předci a vlastní. S indexem plátna (`BoardIndex`) bez průchodu
 *  všemi uzly a pravidly pro každou kartu; výsledek je stejný jako bez něj. */
export function effectiveRules(graph: Graph, state: DesktopState, nodeId: string, index?: BoardIndex): EffectiveRule[] {
  const byId: ReadonlyMap<string, Graph["nodes"][number]> = index?.byId ?? new Map(graph.nodes.map((node) => [node.id, node]));
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
  for (const rule of candidateRules(state, lineage, index)) {
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

/** Pravidla, která mohou kartě platit, v pořadí `state.rules`. Bez indexu všechna. */
function candidateRules(state: DesktopState, lineage: string[], index?: BoardIndex): Rule[] {
  if (!index) return state.rules;
  const slots = [...index.generalRuleSlots, ...lineage.flatMap((id) => index.nodeRuleSlots.get(id) ?? [])];
  return slots.sort((left, right) => left.position - right.position).map((slot) => slot.rule);
}
