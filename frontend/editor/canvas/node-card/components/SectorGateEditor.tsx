import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { nearestSector } from "../logic/sector-status";

export default function SectorGateEditor({ sector, graph, disabled, save }: {
  sector: CanvasNode; graph: Graph; disabled: boolean; save: (node: CanvasNode) => void;
}) {
  return <label className="board-bar__gate">Závěrečná karta: <select aria-label="Závěrečná karta sektoru" disabled={disabled}
    value={sector.gateNodeId ?? ""} onChange={event => {
      const { gateNodeId: _previous, ...node } = sector;
      save(event.target.value ? { ...node, gateNodeId: event.target.value } : node);
    }}>
    <option value="">Nenastavena</option>
    {graph.nodes.filter(n => n.kind === "node" && nearestSector(graph, n) === sector.id).map(n => <option key={n.id} value={n.id}>{n.name}</option>)}
  </select></label>;
}
