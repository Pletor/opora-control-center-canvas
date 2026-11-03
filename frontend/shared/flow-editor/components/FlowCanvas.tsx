import { useEffect, type DragEvent } from "react";
import { Background, BackgroundVariant, Controls, MiniMap, ReactFlow, ReactFlowProvider, useNodesState, useReactFlow, type Connection, type Edge } from "@xyflow/react";
import type { Point, PortRef } from "../logic/flow-types";
import { parseHandle, type FlowCardNode } from "../logic/flow-view";
import { PortActionsContext, type PlusRequest } from "../flow-node/logic/port-actions";
import { PALETTE_DRAG_TYPE } from "../node-palette/logic/palette";
import FlowNodeCard from "../flow-node/components/FlowNodeCard";

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

function Canvas({ nodes: next, edges, readOnly, canConnect, onSelectNode, onSelectEdge, onMove, onConnect, onDropType, onPlus }: Props) {
  const flow = useReactFlow();
  const [nodes, setNodes, onNodesChange] = useNodesState<FlowCardNode>(next);
  // Přestavba uzlů nesmí zahodit změřený rozměr, jinak React Flow schová hrany, než uzly znovu změří.
  useEffect(() => setNodes((prev) => next.map((node) => ({ ...node, measured: prev.find((item) => item.id === node.id)?.measured }))), [next, setNodes]);
  const drop = (event: DragEvent) => {
    const type = event.dataTransfer.getData(PALETTE_DRAG_TYPE);
    if (!type || readOnly) return;
    event.preventDefault();
    onDropType(type, flow.screenToFlowPosition({ x: event.clientX, y: event.clientY }));
  };
  return <div className={`flow-editor__canvas${readOnly ? " flow-editor__canvas--past" : ""}`} data-testid="flow-canvas"
    onDragOver={(event) => { if (!readOnly && event.dataTransfer.types.includes(PALETTE_DRAG_TYPE)) { event.preventDefault(); event.dataTransfer.dropEffect = "copy"; } }} onDrop={drop}>
    <PortActionsContext.Provider value={{ onPlus }}>
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={onNodesChange} fitView fitViewOptions={{ padding: 0.25, maxZoom: 1 }}
        minZoom={0.2} maxZoom={2} nodesConnectable={!readOnly} deleteKeyCode={null} colorMode="dark" zoomOnDoubleClick={false}
        isValidConnection={(c) => { const pair = ends(c); return !!pair && canConnect(pair[0], pair[1]); }}
        onConnect={(c) => { const pair = ends(c); if (pair) onConnect(pair[0], pair[1]); }}
        onNodeClick={(_, node) => { if (!node.data.ghost) onSelectNode(node.data.nodeId); }}
        onEdgeClick={(_, edge) => onSelectEdge(edge.id)} onPaneClick={() => { onSelectNode(null); onSelectEdge(null); }}
        onNodeDragStop={(_, node) => onMove(node.id, node.position)}>
        <Background variant={BackgroundVariant.Dots} gap={20} size={1.2} color="var(--canvas-dot)"/>
        <MiniMap position="bottom-right" pannable zoomable ariaLabel="Minimapa toku" className="flow-editor__minimap" nodeBorderRadius={8}/>
        <Controls position="top-left" showInteractive={false}/>
      </ReactFlow>
    </PortActionsContext.Provider>
  </div>;
}
