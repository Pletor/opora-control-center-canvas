import { useEffect, useMemo, useRef, useState } from "react";
import { ReactFlow, Background, BackgroundVariant, Controls, MarkerType, applyNodeChanges, type Edge, type ReactFlowInstance, type Viewport } from "@xyflow/react";
import type { Graph } from "@/shared/types/logic/types";
import { CATALOG_DRAG_TYPE } from "@/editor/component-library/library-catalog/logic/library-catalog";
import { areaSectorLabel, cardSummary, edgeLook } from "../logic/canvas-model";
import { viewportShowsAllNodes } from "../logic/viewport-visibility";
import ArchitectureCard, { type ArchitectureNode, type CardActions } from "../map-card/components/ArchitectureCard";

const nodeTypes = { architecture: ArchitectureCard };
const DEFAULT_VIEWPORT: Viewport = { x: 50, y: 75, zoom: 0.9 };

type Props = {
  graph: Graph; scopeId: string; editorId: string; selected: string | null; disabled: boolean; revealId: string | null;
  onSelect: (id: string | null) => void; onOpenStructure: (id: string) => void; onOpenEditor: (id: string) => void;
  onAddNode: (parentId: string) => void; onSector: (areaId: string) => void;
  onMove: (id: string, x: number, y: number) => Promise<void>; onConnect: (source: string, target: string) => void;
  onInsert: (id: string, targetId: string | null, point: { x: number; y: number }) => void;
};

/** Stored viewport of this map, or null on the first visit (the map then fits its cards). */
function readViewport(key: string): Viewport | null {
  try {
    const value = JSON.parse(localStorage.getItem(key) ?? "null");
    return value && [value.x, value.y, value.zoom].every(Number.isFinite) ? value : null;
  } catch { return null; }
}

/** Map of one page: areas, sectors and nodes of the open scope, with links between them. */
export default function ArchitectureCanvas(props: Props) {
  const { graph, scopeId, editorId, selected, disabled, revealId } = props;
  const flow = useRef<ReactFlowInstance<ArchitectureNode> | null>(null);
  const stage = useRef<HTMLDivElement | null>(null);
  const latest = useRef(props); latest.current = props;
  const actions = useMemo<CardActions>(() => ({
    select: (id) => latest.current.onSelect(id), openStructure: (id) => latest.current.onOpenStructure(id),
    openEditor: (id) => latest.current.onOpenEditor(id), addNode: (id) => latest.current.onAddNode(id), addSector: (id) => latest.current.onSector(id),
  }), []);
  const make = (): ArchitectureNode[] => graph.nodes.filter((node) => node.parentId === scopeId).map((node) => {
    const area = node.kind === "area";
    return {
      id: node.id, type: "architecture", position: { x: node.x, y: node.y }, selected: node.id === selected,
      zIndex: area ? -1 : 1, style: area ? { width: node.size?.w ?? 720, height: node.size?.h ?? 480 } : { width: 270 },
      data: { node, disabled, actions, summary: area || node.kind === "comment" ? null : cardSummary(node, graph), areaLabel: area ? areaSectorLabel(node, graph) : null },
    };
  });
  const [nodes, setNodes] = useState<ArchitectureNode[]>(make);
  const viewportKey = `opora:architecture-viewport:${editorId}:${scopeId}`;
  const [viewport] = useState<Viewport | null>(() => readViewport(viewportKey));
  // Carry measured sizes across rebuilds; without them React Flow remounts cards and inputs lose focus.
  useEffect(() => {
    setNodes((old) => make().map((next) => { const prior = old.find((item) => item.id === next.id); return prior?.measured ? { ...next, measured: prior.measured } : next; }));
  }, [graph, scopeId, selected, disabled]);
  useEffect(() => {
    if (!revealId) return;
    let raf = 0; let attempts = 0;
    function reveal() {
      const node = flow.current?.getNode(revealId!);
      if (!node?.measured?.width || !node.measured.height) { if (++attempts < 90) raf = requestAnimationFrame(reveal); return; }
      void flow.current?.setCenter(node.position.x + node.measured.width / 2, node.position.y + node.measured.height / 2, { zoom: Math.min(flow.current.getZoom(), 1) });
    }
    raf = requestAnimationFrame(reveal); return () => cancelAnimationFrame(raf);
  }, [revealId]);
  const ids = new Set(nodes.map((node) => node.id));
  const edges: Edge[] = graph.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target)).map((edge) => {
    const look = edgeLook(edge, graph);
    return { id: edge.id, source: edge.source, target: edge.target, label: look.label, className: "page-editor__edge",
      markerEnd: { type: MarkerType.ArrowClosed, color: look.color, width: 16, height: 16 },
      style: { stroke: look.color, strokeWidth: 2, strokeDasharray: look.dashed ? "7 6" : undefined } };
  });
  return <div className="page-editor__canvas" data-testid="architecture-canvas" ref={stage}
    onDragOver={(event) => { if (!disabled && event.dataTransfer.types.includes(CATALOG_DRAG_TYPE)) { event.preventDefault(); event.dataTransfer.dropEffect = "copy"; } }}
    onDrop={(event) => {
      if (disabled || !event.dataTransfer.types.includes(CATALOG_DRAG_TYPE) || !flow.current) return;
      event.preventDefault();
      const target = event.target instanceof Element ? event.target.closest(".react-flow__node")?.getAttribute("data-id") ?? null : null;
      const point = flow.current.screenToFlowPosition({ x: event.clientX, y: event.clientY });
      props.onInsert(event.dataTransfer.getData(CATALOG_DRAG_TYPE), target, { x: point.x - 135, y: point.y - 45 });
    }}>
    <ReactFlow<ArchitectureNode> nodes={nodes} edges={edges} nodeTypes={nodeTypes} colorMode="dark"
      onInit={(instance) => {
        flow.current = instance;
        // A stored viewport that shows no card (cards moved or window resized) is dropped in favour of fitting the map.
        if (!viewport || !stage.current) return;
        const size = { width: stage.current.clientWidth, height: stage.current.clientHeight };
        const boxes = latest.current.graph.nodes.filter((node) => node.parentId === scopeId).map((node) => ({ x: node.x, y: node.y, w: node.kind === "area" ? node.size?.w ?? 720 : 270, h: node.kind === "area" ? node.size?.h ?? 480 : 90 }));
        if (!viewportShowsAllNodes(viewport, size, boxes)) requestAnimationFrame(() => { void instance.fitView({ maxZoom: 1, padding: 0.15 }); });
      }} defaultViewport={viewport ?? DEFAULT_VIEWPORT} fitView={!viewport} fitViewOptions={{ maxZoom: 1, padding: 0.15 }} minZoom={0.2} maxZoom={1.6} elevateNodesOnSelect={false}
      onNodesChange={(changes) => setNodes((old) => applyNodeChanges(changes, old))} nodesDraggable={!disabled} nodesConnectable={!disabled}
      onNodeClick={(_, node) => props.onSelect(node.id)} onPaneClick={() => props.onSelect(null)}
      onNodeDoubleClick={(_, node) => { if (node.data.node.kind === "node" || node.data.node.kind === "sector") props.onOpenStructure(node.id); }}
      onNodeDragStop={(_, node) => { void props.onMove(node.id, node.position.x, node.position.y).catch(() => setNodes(make())); }}
      onConnect={(connection) => { if (connection.source && connection.target) props.onConnect(connection.source, connection.target); }}
      onMoveEnd={(_, next) => { try { localStorage.setItem(viewportKey, JSON.stringify(next)); } catch { /* Navigation works without storage. */ } }}
      deleteKeyCode={null}>
      <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#294454"/>
      <Controls showInteractive={false}/>
    </ReactFlow>
  </div>;
}
