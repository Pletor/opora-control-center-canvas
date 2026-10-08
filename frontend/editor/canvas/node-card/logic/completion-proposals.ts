import type { Graph } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import { setDone } from "@/editor/node-detail/tree/logic/tree-model";

export function proposalsIn(graph: Graph, state: DesktopState, parent: string | null) {
  const pending = [parent];
  const visited = new Set<string>();
  const proposals: { id: string; name: string; note: string }[] = [];
  while (pending.length) {
    const current = pending.pop();
    for (const node of graph.nodes) {
      if (node.parentId !== current || visited.has(node.id)) continue;
      visited.add(node.id); pending.push(node.id);
      const done = state.nodes[node.id]?.done;
      if ((node.kind === "node" || node.kind === "sector") && done?.by === "agent" && !done.confirmed) proposals.push({ id: node.id, name: node.name, note: done.note });
    }
  }
  return proposals;
}
export const proposalCount = (graph: Graph, state: DesktopState, parent: string | null) => proposalsIn(graph, state, parent).length;

export const confirmProposal = (nodeId: string) => (state: DesktopState): DesktopState => {
  const done = state.nodes[nodeId]?.done;
  if (!done || done.confirmed || done.by !== "agent") throw new Error("Návrh uzavření už není aktuální. Obnovte kartu.");
  return setDone(nodeId, { confirmed: true, by: "human" })(state);
};
