import { useEffect, useRef, useState, memo } from "react";
import { useDesktopAppearance } from "./DesktopThemeControls";
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
import type { SurfaceSettings } from "./workspace-settings";
import type { Graph } from "./types";
const Card = memo(function Card({ id, data, selected }: NodeProps) {
  const rename = data.rename as
    | { editing: boolean; commit: (name: string) => void; cancel: () => void; start: () => void }
    | undefined;
  const field = useRef<HTMLInputElement>(null);
  // React Flow kartu do změření skrývá, proto se fokus zkouší i v dalších snímcích.
  useEffect(() => {
    if (!rename?.editing) return;
    let frame = 0;
    let attempts = 0;
    const take = () => {
      if (field.current && document.activeElement !== field.current) {
        field.current.focus();
        field.current.select();
      }
      attempts += 1;
      if (field.current && document.activeElement !== field.current && attempts < 20)
        frame = requestAnimationFrame(take);
    };
    take();
    return () => cancelAnimationFrame(frame);
  }, [rename?.editing]);
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
      {rename?.editing ? (
        <input
          ref={field}
          className="nodrag card-rename"
          aria-label="Jméno uzlu na plátně"
          data-testid={"card-rename-" + id}
          defaultValue={String(data.name)}
          autoFocus
          maxLength={160}
          onFocus={(e) => e.currentTarget.select()}
          onKeyDown={(e) => {
            e.stopPropagation();
            if (e.nativeEvent.isComposing) return;
            if (e.key === "Enter") rename.commit(e.currentTarget.value);
            if (e.key === "Escape") rename.cancel();
          }}
          onBlur={(e) => rename.commit(e.currentTarget.value)}
        />
      ) : (
        <strong
          title="Dvojklik přejmenuje přímo na plátně"
          onDoubleClick={(e) => {
            e.stopPropagation();
            rename?.start();
          }}
        >
          {String(data.name)}
        </strong>
      )}
      <p>{String(data.purpose || "Podstata zatím není popsána.")}</p>
      <div className="node-foot">Rozkliknout → vnitřní plátno</div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
});
const nodeTypes = { canvas: Card };
export default function Board({
  graph,
  settings,
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
  editing,
  onEditing,
  onRename,
  onCreateAt,
}: {
  graph: Graph;
  settings: SurfaceSettings;
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
  /** Uzel právě přejmenovaný přímo na kartě. */
  editing: string | null;
  onEditing: (id: string | null) => void;
  onRename: (id: string, name: string) => void;
  /** Dvojklik na prázdné plátno vytvoří uzel na daném místě vrstvy. */
  onCreateAt: (x: number, y: number) => void;
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
          rename: {
            editing: editing === n.id,
            start: () => !disabled && onEditing(n.id),
            cancel: () => onEditing(null),
            commit: (name: string) => {
              onEditing(null);
              if (name.trim() && name.trim() !== n.name) onRename(n.id, name.trim());
            },
          },
        },
      }));
  const [nodes, setNodes] = useState<Node[]>(make);
  useEffect(() => setNodes(make()), [graph, parent, selected, editing, disabled]);
  const [viewport, setViewport] = useState<Viewport>(() => {
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
    <div
      className="board-surface"
      data-testid="board-surface"
      /* Capture fáze: d3 zoom zastavuje dvojklik na plátně dřív, než by probublal. */
      onDoubleClickCapture={(event) => {
        // Jen prázdné plátno: dvojklik na kartu zůstává vstupem do vnitřního plátna.
        const target = event.target as HTMLElement;
        if (disabled || !target.classList.contains("react-flow__pane")) return;
        const rect = event.currentTarget.getBoundingClientRect();
        onCreateAt(
          Math.round((event.clientX - rect.left - viewport.x) / viewport.zoom) - 130,
          Math.round((event.clientY - rect.top - viewport.y) / viewport.zoom) - 50,
        );
      }}
    >
    <ReactFlow
      colorMode={useDesktopAppearance().theme}
      nodes={nodes}
      edges={edges.map((e) => ({ ...e, selected: e.id === selectedEdge }))}
      nodeTypes={nodeTypes}
      defaultViewport={viewport}
      minZoom={0.15}
      maxZoom={2}
      nodesDraggable={!disabled}
      snapToGrid={settings.snap}
      snapGrid={[settings.gridSize, settings.gridSize]}
      nodesConnectable={!disabled}
      deleteKeyCode={null}
      zoomOnDoubleClick={false}
      onNodesChange={(changes) => setNodes((n) => applyNodeChanges(changes, n))}
      onNodeClick={(_, n) => onSelect(n.id)}
      onEdgeClick={(_, edge) => onSelectEdge(edge.id)}
      onPaneClick={() => onSelectEdge(null)}
      onNodeDoubleClick={(_, n) => onEnter(n.id)}
      onNodeDragStop={(_, n) => onPosition(n.id, n.position.x, n.position.y)}
      onConnect={onConnect}
      onMoveEnd={(_, v) => {
        setViewport(v);
        localStorage.setItem("viewport:" + scope, JSON.stringify(v));
      }}
    >
      {settings.showGrid && (
        <Background color="var(--canvas-dot)" gap={settings.gridSize} />
      )}
      <Controls showInteractive={false} />
      <MiniMap
        nodeColor={(n) => (n.data.kind === "sector" ? "#5f947f" : "#526b89")}
        maskColor="rgba(15,19,24,.75)"
      />
    </ReactFlow>
      {!disabled && (
        <p className="board-hint" data-testid="board-hint">
          Dvojklik na prázdné plátno = nový uzel · dvojklik na název karty = přejmenovat
        </p>
      )}
    </div>
  );
}
