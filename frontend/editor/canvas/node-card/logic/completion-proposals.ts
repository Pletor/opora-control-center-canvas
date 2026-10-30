import type { Graph } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import { setDone } from "@/editor/node-detail/tree/logic/tree-model";
import type { BoardIndex } from "@/editor/canvas/board/logic/board-index";

/** Návrhy uzavření od agenta pod rodičem (do hloubky). S indexem plátna (`BoardIndex`) jde přes seznamy
 *  dětí místo průchodu všemi uzly pro každého rodiče; pořadí i výsledek jsou stejné. */
export function proposalsIn(graph: Graph, state: DesktopState, parent: string | null, index?: BoardIndex) {
  const pending = [parent];
  const visited = new Set<string>();
  const proposals: { id: string; name: string; note: string }[] = [];
  while (pending.length) {
    const current = pending.pop();
    for (const node of index ? index.children.get(current ?? null) ?? [] : graph.nodes) {
      if (node.parentId !== current || visited.has(node.id)) continue;
      visited.add(node.id); pending.push(node.id);
      const done = state.nodes[node.id]?.done;
      if ((node.kind === "node" || node.kind === "sector") && done?.by === "agent" && !done.confirmed) proposals.push({ id: node.id, name: node.name, note: done.note });
    }
  }
  return proposals;
}
export const proposalCount = (graph: Graph, state: DesktopState, parent: string | null, index?: BoardIndex) =>
  proposalsIn(graph, state, parent, index).length;

export const confirmProposal = (nodeId: string) => (state: DesktopState): DesktopState => {
  const done = state.nodes[nodeId]?.done;
  if (!done || done.confirmed || done.by !== "agent") throw new Error("Návrh uzavření už není aktuální. Obnovte kartu.");
  return setDone(nodeId, { confirmed: true, by: "human" })(state);
};

/** Lidské uzavření karty po sloučení PR (akce `close_card` z agent-state): stejný zápis `done` jako potvrzení
 *  návrhu, jen bez návrhu agenta. Serverová brána uzavření rozhoduje dál; tady jen nepřepíšeme hotové. */
export const closeCardAfterMerge = (nodeId: string, note: string) => (state: DesktopState): DesktopState => {
  if (state.nodes[nodeId]?.done?.confirmed) throw new Error("Karta už je uzavřená. Obnovte kartu.");
  return setDone(nodeId, { confirmed: true, by: "human", note })(state);
};
