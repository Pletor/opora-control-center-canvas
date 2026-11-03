import { useEffect } from "react";
import { ReactFlowProvider, useNodesState, type Connection, type Edge } from "@xyflow/react";
import type { Point, PortRef } from "../logic/flow-types";
import { parseHandle, type FlowCardNode } from "../logic/flow-view";
import { PortActionsContext, type PlusRequest } from "../flow-node/logic/port-actions";
import FlowNodeCard from "../flow-node/components/FlowNodeCard";
import FlowSurface, { type SurfaceView } from "./FlowSurface";

const nodeTypes = { "flow-card": FlowNodeCard };

type Props = {
  nodes: FlowCardNode[]; edges: Edge[]; readOnly: boolean;
  canConnect: (a: PortRef, b: PortRef) => boolean;
  onSelectNode: (id: string | null) => void; onSelectEdge: (id: string | null) => void; onMove: (id: string, at: Point) => void;
  onConnect: (a: PortRef, b: PortRef) => void; onDropType: (type: string, at: Point) => void; onPlus: (request: PlusRequest) => void;
};

const ends = (c: Connection | Edge) => {
  const a = parseHandle(c.source, c.sourceHandle), b = parseHandle(c.target, c.targetHandle);
  return a && b ? [a, b] as const : null;
};

/** Plátno toku nad React Flow: tečkovaná mřížka, zoom, minimapa, tah uzlů, tah vazby mezi kompatibilními porty a
 * puštění typu z palety. Uzly drží lokálně jen kvůli změřeným rozměrům a tahu; poloha jde rodiči až po puštění. */
export default function FlowCanvas(props: Props) {
  return <ReactFlowProvider><Canvas {...props}/></ReactFlowProvider>;
}

const VIEW: SurfaceView = { minZoom: 0.2, maxZoom: 2, fitPadding: 0.25, dotGap: 20, dotColor: "var(--canvas-dot)", controls: "top-left", minimapLabel: "Minimapa toku", minimapClass: "flow-editor__minimap" };

function Canvas({ nodes: next, edges, readOnly, canConnect, onSelectNode, onSelectEdge, onMove, onConnect, onDropType, onPlus }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState<FlowCardNode>(next);
  // Přestavba uzlů nesmí zahodit změřený rozměr, jinak React Flow schová hrany, než uzly znovu změří.
  useEffect(() => setNodes((prev) => next.map((node) => ({ ...node, measured: prev.find((item) => item.id === node.id)?.measured }))), [next, setNodes]);
  return <PortActionsContext.Provider value={{ onPlus }}>
    <FlowSurface nodes={nodes} edges={edges} nodeTypes={nodeTypes} view={VIEW} onNodesChange={onNodesChange} onDropType={readOnly ? undefined : onDropType}
      rootProps={{ className: `flow-editor__canvas${readOnly ? " flow-editor__canvas--past" : ""}`, "data-testid": "flow-canvas" }}
      flowProps={{
        nodesConnectable: !readOnly,
        isValidConnection: (c) => { const pair = ends(c); return !!pair && canConnect(pair[0], pair[1]); },
        onConnect: (c) => { const pair = ends(c); if (pair) onConnect(pair[0], pair[1]); },
        onNodeClick: (_, node) => { if (!node.data.ghost) onSelectNode(node.data.nodeId); },
        onEdgeClick: (_, edge) => onSelectEdge(edge.id), onPaneClick: () => { onSelectNode(null); onSelectEdge(null); },
        onNodeDragStop: (_, node) => onMove(node.id, node.position),
      }}/>
  </PortActionsContext.Provider>;
}
