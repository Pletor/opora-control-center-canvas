import { useEffect } from "react";
import { ReactFlowProvider, useNodesState, type Connection, type Edge, type Node } from "@xyflow/react";
import type { Point, PortRef } from "../logic/flow-types";
import { parseHandle, type FlowCardNode } from "../logic/flow-view";
import { GROUP_PREFIX, NOTE_PREFIX, type FlowGroupNode, type FlowNoteNode } from "../logic/frame-view";
import { PortActionsContext, type PlusRequest } from "../flow-node/logic/port-actions";
import { FrameActionsContext, type FrameActions } from "../flow-frame/logic/frame-actions";
import FlowNodeCard from "../flow-node/components/FlowNodeCard";
import FlowNoteCard from "../flow-frame/components/FlowNoteCard";
import FlowGroupFrame from "../flow-frame/components/FlowGroupFrame";
import FlowSurface, { type SurfaceView } from "./FlowSurface";

const nodeTypes = { "flow-card": FlowNodeCard, "flow-note": FlowNoteCard, "flow-group": FlowGroupFrame };
export type CanvasNode = FlowCardNode | FlowNoteNode | FlowGroupNode;

type Props = {
  nodes: CanvasNode[]; edges: Edge[]; readOnly: boolean; frames?: FrameActions;
  canConnect: (a: PortRef, b: PortRef) => boolean;
  onSelectNode: (id: string | null) => void; onSelectEdge: (id: string | null) => void; onMove: (id: string, at: Point) => void;
  onConnect: (a: PortRef, b: PortRef) => void; onDropType: (type: string, at: Point) => void; onPlus: (request: PlusRequest) => void;
  /** Rámec vybraný klikem (id bez předpony) a uzly vybrané tahem s Shiftem nebo Ctrl+klikem (pro „Rámec z výběru“). */
  onSelectGroup?: (id: string) => void; onSelection?: (nodeIds: string[]) => void; onMoveNote?: (id: string, at: Point) => void;
};

const ends = (c: Connection | Edge) => {
  const a = parseHandle(c.source, c.sourceHandle), b = parseHandle(c.target, c.targetHandle);
  return a && b ? [a, b] as const : null;
};

/** Plátno toku nad React Flow: tečkovaná mřížka, zoom, minimapa, tah uzlů, tah vazby mezi kompatibilními porty a
 * puštění typu z palety. Uzly drží lokálně jen kvůli změřeným rozměrům a tahu; poloha jde rodiči až po puštění.
 * Za kartami leží sticky poznámky a rámce skupin (`flow-frame/`). */
export default function FlowCanvas(props: Props) {
  return <ReactFlowProvider><Canvas {...props}/></ReactFlowProvider>;
}

const VIEW: SurfaceView = { minZoom: 0.2, maxZoom: 2, fitPadding: 0.25, dotGap: 20, dotColor: "var(--canvas-dot)", controls: "top-left", minimapLabel: "Minimapa toku", minimapClass: "flow-editor__minimap" };
const NO_FRAMES: FrameActions = { onNote: () => {}, onToggleGroup: () => {} };

function Canvas({ nodes: next, edges, readOnly, frames, canConnect, onSelectNode, onSelectEdge, onMove, onConnect, onDropType, onPlus, onSelectGroup, onSelection, onMoveNote }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState<CanvasNode>(next);
  // Přestavba uzlů nesmí zahodit změřený rozměr, jinak React Flow schová hrany, než uzly znovu změří.
  useEffect(() => setNodes((prev) => next.map((node) => ({ ...node, measured: prev.find((item) => item.id === node.id)?.measured }) as CanvasNode)), [next, setNodes]);
  const click = (node: Node) => {
    if (node.id.startsWith(GROUP_PREFIX)) onSelectGroup?.(node.id.slice(GROUP_PREFIX.length));
    else if (node.type === "flow-card" && !(node as FlowCardNode).data.ghost) onSelectNode((node as FlowCardNode).data.nodeId);
  };
  return <PortActionsContext.Provider value={{ onPlus }}>
    <FrameActionsContext.Provider value={frames ?? NO_FRAMES}>
      <FlowSurface nodes={nodes} edges={edges} nodeTypes={nodeTypes} view={VIEW} onNodesChange={onNodesChange} onDropType={readOnly ? undefined : onDropType}
        rootProps={{ className: `flow-editor__canvas${readOnly ? " flow-editor__canvas--past" : ""}`, "data-testid": "flow-canvas" }}
        flowProps={{
          nodesConnectable: !readOnly,
          isValidConnection: (c) => { const pair = ends(c); return !!pair && canConnect(pair[0], pair[1]); },
          onConnect: (c) => { const pair = ends(c); if (pair) onConnect(pair[0], pair[1]); },
          onNodeClick: (_, node) => click(node),
          onEdgeClick: (_, edge) => onSelectEdge(edge.id), onPaneClick: () => { onSelectNode(null); onSelectEdge(null); },
          onSelectionChange: onSelection && (({ nodes: picked }) => onSelection(picked.filter((node) => node.type === "flow-card").map((node) => node.id))),
          onNodeDragStop: (_, node) => node.id.startsWith(NOTE_PREFIX) ? onMoveNote?.(node.id.slice(NOTE_PREFIX.length), node.position) : onMove(node.id, node.position),
        }}/>
    </FrameActionsContext.Provider>
  </PortActionsContext.Provider>;
}
