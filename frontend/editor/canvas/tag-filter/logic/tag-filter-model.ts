// Štítky viditelné vrstvy: sjednocení štítků bloků všech karet ve vrstvě, s počtem karet, které štítek nesou.
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import { nodeWorkflowOf } from "@/shared/desktop-state/logic/types";
import type { Graph } from "@/shared/types/logic/types";
import { nodeTags } from "@/editor/canvas/node-card/logic/card-model";

export function tagCounts(graph: Graph, parent: string | null, state: DesktopState): { tag: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const node of graph.nodes) {
    if (node.parentId !== parent || node.kind === "comment" || node.kind === "area") continue;
    for (const tag of nodeTags(nodeWorkflowOf(state, node.id))) counts.set(tag, (counts.get(tag) ?? 0) + 1);
  }
  return [...counts.entries()].map(([tag, count]) => ({ tag, count })).sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag, "cs"));
}
