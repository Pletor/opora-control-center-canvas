import { useMemo, useState, useEffect } from "react";
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
} from "@xyflow/react";
import type { Graph } from "./types";
import type { SurfaceSettings } from "./workspace-settings";
import { projectMapModel } from "./project-map";
import { useDesktopAppearance } from "./DesktopThemeControls";
function MapCard({ data, selected }: NodeProps) {
  return (
    <div className={"map-card " + (selected ? "selected " : "") + data.kind}>
      {data.entityId !== null && (
        <Handle type="target" position={Position.Left} />
      )}
      <small>
        {data.kind === "project"
          ? "PROJEKT"
          : data.kind === "sector"
            ? "SEKTOR"
            : "UZEL"}
      </small>
      <strong>{String(data.label)}</strong>
      <Handle
        type="source"
        position={Position.Right}
        isConnectable={data.entityId !== null}
      />
    </div>
  );
}
const nodeTypes = { mapCard: MapCard };
export default function ProjectMap({
  graph,
  projectName,
  selected,
  selectedEdge,
  settings,
  readOnly,
  onSelect,
  onSelectEdge,
  onEnter,
  onConnect,
}: {
  graph: Graph;
  projectName: string;
  selected: string | null;
  selectedEdge: string | null;
  settings: SurfaceSettings;
  readOnly: boolean;
  onSelect: (id: string | null) => void;
  onSelectEdge: (id: string | null) => void;
  onEnter: (id: string) => void;
  onConnect: (c: Connection) => void;
}) {
  const model = useMemo(
    () => projectMapModel(graph, projectName),
    [graph, projectName],
  );
  const { theme } = useDesktopAppearance();
  type MapNode = Node<(typeof model.nodes)[number], "mapCard">;
  const makeNodes = (previous: MapNode[] = []): MapNode[] =>
    model.nodes.map((n) => ({
      ...previous.find((old) => old.id === n.id),
      id: n.id,
      type: "mapCard",
      position: { x: n.x, y: n.y },
      selected: n.entityId !== null && n.entityId === selected,
      connectable: n.entityId !== null && !readOnly,
      data: n,
    }));
  const [nodes, setNodes] = useState<MapNode[]>(() => makeNodes());
  useEffect(
    () => setNodes((old) => makeNodes(old)),
    [model, selected, readOnly],
  );
  const edges = model.edges.map((e) => ({
    ...e,
    type: "smoothstep",
    selected: e.kind === "link" && e.entityId === selectedEdge,
    selectable: e.kind === "link",
    style: {
      stroke: e.kind === "contains" ? "var(--map-contains)" : "var(--accent)",
      strokeDasharray: e.kind === "contains" ? "6 5" : undefined,
      strokeWidth: 2,
    },
  }));
  return (
    <div className="project-map" data-testid="project-map">
      <ReactFlow
        nodes={nodes}
        onNodesChange={(changes) =>
          setNodes((old) => applyNodeChanges(changes, old))
        }
        edges={edges}
        nodeTypes={nodeTypes}
        colorMode={theme}
        fitView
        autoPanOnNodeFocus={false}
        zoomOnDoubleClick={false}
        minZoom={0.05}
        maxZoom={1.5}
        nodesDraggable={false}
        nodesConnectable={!readOnly}
        deleteKeyCode={null}
        onNodeClick={(_, n) => onSelect(n.data.entityId)}
        onNodeDoubleClick={(_, n) => {
          if (n.data.entityId) onEnter(n.data.entityId);
        }}
        onEdgeClick={(_, e) => {
          if (e.entityId) onSelectEdge(e.entityId);
        }}
        onPaneClick={() => onSelect(null)}
        onConnect={(c) => {
          const source = model.nodes.find((n) => n.id === c.source)?.entityId;
          const target = model.nodes.find((n) => n.id === c.target)?.entityId;
          if (source && target) onConnect({ ...c, source, target });
        }}
      >
        {settings.showGrid && (
          <Background gap={settings.gridSize} color="var(--canvas-dot)" />
        )}
        <Controls showInteractive={false} />
        <MiniMap nodeColor={theme === "light" ? "#b9c9c8" : "#526b89"} maskColor={theme === "light" ? "rgba(245,243,238,.7)" : "rgba(15,19,24,.7)"} />
      </ReactFlow>
    </div>
  );
}
