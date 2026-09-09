import { useEffect, useState, memo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  applyNodeChanges,
  type Node,
  type NodeProps,
  type Connection,
  type Viewport,
} from "@xyflow/react";
import type { Graph } from "./types";
const Card = memo(function Card({ data, selected }: NodeProps) {
  return (
    <div
      className={
        "canvas-card " +
        (data.kind === "sector" ? "sector" : "") +
        (selected ? " selected" : "")
      }
    >
      <Handle type="target" position={Position.Left} />
      <div className="node-kind">
        {data.kind === "sector" ? "SEKTOR" : "UZEL"}
        <span>{String(data.children)} poduzlů</span>
      </div>
      <strong>{String(data.name)}</strong>
      <p>{String(data.purpose || "Podstata zatím není popsána.")}</p>
      <div className="node-foot">Rozkliknout → vnitřní plátno</div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
});
const nodeTypes = { canvas: Card };
export default function Board({
  graph,
  parent,
  selected,
  scope,
  disabled,
  onSelect,
  selectedEdge,
  onSelectEdge,
  onEnter,
  onPosition,
  onConnect,
}: {
  graph: Graph;
  parent: string | null;
  selected: string | null;
  scope: string;
  disabled: boolean;
  onSelect: (id: string) => void;
  selectedEdge: string | null;
  onSelectEdge: (id: string | null) => void;
  onEnter: (id: string) => void;
  onPosition: (id: string, x: number, y: number) => void;
  onConnect: (c: Connection) => void;
}) {
  const make = () =>
    graph.nodes
      .filter((n) => n.parentId === parent)
      .map((n) => ({
        id: n.id,
        type: "canvas",
        position: { x: n.x, y: n.y },
        selected: n.id === selected,
        data: {
          name: n.name,
          purpose: n.purpose,
          kind: n.kind,
          children: graph.nodes.filter((c) => c.parentId === n.id).length,
        },
      }));
  const [nodes, setNodes] = useState<Node[]>(make);
  useEffect(() => setNodes(make()), [graph, parent, selected]);
  const [viewport] = useState<Viewport>(() => {
    try {
      return (
        JSON.parse(localStorage.getItem("viewport:" + scope) ?? "null") ?? {
          x: 60,
          y: 90,
          zoom: 1,
        }
      );
    } catch {
      return { x: 60, y: 90, zoom: 1 };
    }
  });
  const ids = new Set(nodes.map((n) => n.id));
  const edges = graph.edges.filter(
    (e) => ids.has(e.source) && ids.has(e.target),
  );
  return (
    <ReactFlow
      colorMode="dark"
      nodes={nodes}
      edges={edges.map((e) => ({ ...e, selected: e.id === selectedEdge }))}
      nodeTypes={nodeTypes}
      defaultViewport={viewport}
      minZoom={0.15}
      maxZoom={2}
      nodesDraggable={!disabled}
      nodesConnectable={!disabled}
      deleteKeyCode={null}
      onNodesChange={(changes) => setNodes((n) => applyNodeChanges(changes, n))}
      onNodeClick={(_, n) => onSelect(n.id)}
      onEdgeClick={(_, edge) => onSelectEdge(edge.id)}
      onPaneClick={() => onSelectEdge(null)}
      onNodeDoubleClick={(_, n) => onEnter(n.id)}
      onNodeDragStop={(_, n) => onPosition(n.id, n.position.x, n.position.y)}
      onConnect={onConnect}
      onMoveEnd={(_, v) =>
        localStorage.setItem("viewport:" + scope, JSON.stringify(v))
      }
    >
      <Background color="#303a43" gap={24} />
      <Controls showInteractive={false} />
      <MiniMap
        nodeColor={(n) => (n.data.kind === "sector" ? "#5f947f" : "#526b89")}
        maskColor="rgba(15,19,24,.75)"
      />
    </ReactFlow>
  );
}
