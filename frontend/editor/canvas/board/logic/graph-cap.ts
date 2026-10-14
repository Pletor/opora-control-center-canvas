// Strop velikosti grafu, který UI ukáže dopředu (oprava 8 v docs/navrhy/2026-10-14-vykon-platna.md). Server
// větší graf nebo stav odmítne celý, takže lišta plátna od 80 % stropu tiše ukáže, kolik zbývá, a v titulku
// řekne, že je čas projekt rozdělit. Čísla musí sedět se serverem:
// - uzly a vazby grafu: `backend/canvas/graph.py` (`len(nodes) > 2000`, `len(edges) > 4000`),
// - uzly stavu: `backend/editor/agent_memory/desktop_v3_state.py` (`MAX_NODES = 2000`).
import type { Graph } from "@/shared/types/logic/types";

export const MAX_GRAPH_NODES = 2000;
export const MAX_GRAPH_EDGES = 4000;
export const MAX_STATE_NODES = 2000;
/** Od jakého podílu stropu se varování ukáže. */
export const CAP_WARN_FROM = 0.8;

export type CapWarning = { text: string; title: string };

/** Čísla s mezerou po tisících („1 640“), nezávisle na jazyku prohlížeče. */
export const groupThousands = (value: number) => String(value).replace(/\B(?=(\d{3})+(?!\d))/g, " ");

/** Varování u stropu, nebo `null`, dokud je graf i stav pod 80 %. Ukáže tu míru, která je blíž stropu. */
export function capWarning(graph: Pick<Graph, "nodes" | "edges">, stateNodes = 0): CapWarning | null {
  const nodes = Math.max(graph.nodes.length, stateNodes);
  const nodeLimit = graph.nodes.length >= stateNodes ? MAX_GRAPH_NODES : MAX_STATE_NODES;
  const nodeShare = nodes / nodeLimit;
  const edgeShare = graph.edges.length / MAX_GRAPH_EDGES;
  if (Math.max(nodeShare, edgeShare) < CAP_WARN_FROM) return null;
  const text = nodeShare >= edgeShare
    ? `Uzlů ${groupThousands(nodes)} / ${groupThousands(nodeLimit)}`
    : `Vazeb ${groupThousands(graph.edges.length)} / ${groupThousands(MAX_GRAPH_EDGES)}`;
  return {
    text,
    title: `Projekt se blíží stropu (${groupThousands(MAX_GRAPH_NODES)} uzlů, ${groupThousands(MAX_GRAPH_EDGES)} vazeb). ` +
      "Nad stropem server změnu odmítne celou; je čas rozdělit projekt na menší.",
  };
}
