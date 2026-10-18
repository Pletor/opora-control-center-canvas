// Štíhlý zápis posunu karet (oprava 8 v docs/navrhy/2026-10-14-vykon-platna.md): když se graf liší
// jen pozicemi existujících uzlů, jde na server POST /api/graph/positions s {id, x, y} a digestem
// místo celého grafu (stovky kB). Server odpoví pohledem bez grafu; nový graf si klient složí sám
// z výchozího pohledu a uložených pozic. Cokoli jiného (nový uzel, vazba, krok zpět) jde celým grafem.
import { api, type Graph, type View } from "@/shared/types/logic/types";

export type Position = { id: string; x: number; y: number };
/** Odpověď POST /api/graph/positions: pohled bez grafu a pozice, jak je server uložil. */
export type PositionsResponse = Omit<View, "graph"> & { positions: Position[] };

const withoutPosition = ({ x: _x, y: _y, ...rest }: Graph["nodes"][number]) => rest;

/**
 * Pozice, kterými se `after` liší od `before`, když je to jediný rozdíl (stejné uzly ve stejném
 * pořadí, stejné vazby, jinak nezměněná pole). Jinak `null`, stejně jako při žádné změně.
 */
export function positionChanges(before: Graph, after: Graph): Position[] | null {
  if (before.nodes.length !== after.nodes.length) return null;
  if (before.edges !== after.edges && JSON.stringify(before.edges) !== JSON.stringify(after.edges)) return null;
  const changes: Position[] = [];
  for (let i = 0; i < after.nodes.length; i++) {
    const old = before.nodes[i];
    const next = after.nodes[i];
    if (old === next) continue;
    if (old.id !== next.id || JSON.stringify(withoutPosition(old)) !== JSON.stringify(withoutPosition(next))) return null;
    if (old.x !== next.x || old.y !== next.y) changes.push({ id: next.id, x: Math.round(next.x), y: Math.round(next.y) });
  }
  return changes.length ? changes : null;
}

/** Pohled po uložení pozic: výchozí graf s uloženými pozicemi a hlavička (digest, revize architektury…) ze serveru. */
export function withPositions(view: View, response: PositionsResponse): View {
  const { positions, ...head } = response;
  const moved = new Map(positions.map((item) => [item.id, item]));
  const nodes = view.graph.nodes.map((node) => {
    const hit = moved.get(node.id);
    return hit ? { ...node, x: hit.x, y: hit.y } : node;
  });
  return { ...view, ...head, graph: { ...view.graph, nodes } };
}

export type GraphSaveRequest = { project: string; workspace: string; graph: Graph; digest: string; undo: boolean };

/**
 * Uložení grafu plátna: čistý posun karet štíhle, jinak celý graf jako dřív. `view` je pohled,
 * ze kterého změna vyšla (jeho digest jde na server jako `digest`).
 */
export async function saveCanvasGraph(view: View, request: GraphSaveRequest): Promise<View> {
  const positions = request.undo ? null : positionChanges(view.graph, request.graph);
  if (!positions) return api<View>("/api/graph", request);
  const { project, workspace, digest } = request;
  return withPositions(view, await api<PositionsResponse>("/api/graph/positions", { project, workspace, digest, positions }));
}
