import { useEffect, useMemo, useRef, useState } from "react";
import { ReactFlow, Background, BackgroundVariant, Controls, MarkerType, applyNodeChanges, type Edge, type ReactFlowInstance, type Viewport } from "@xyflow/react";
import type { Graph } from "@/shared/types/logic/types";
import { CATALOG_DRAG_TYPE } from "@/editor/component-library/library-catalog/logic/library-catalog";
import { areaSectorLabel, cardBodies, cardSummary, CARD_WIDTH, edgeLook } from "../logic/canvas-model";
import { dropCard, type Rect } from "@/editor/canvas/area/logic/area-growth";
import { useAreaGrowth } from "@/editor/canvas/area/logic/use-area-growth";
import { viewportShowsAllNodes } from "../logic/viewport-visibility";
import PortZoomVar from "@/shared/flow-ports/components/PortZoomVar";
import ArchitectureCard, { type ArchitectureNode, type CardActions } from "../map-card/components/ArchitectureCard";

const nodeTypes = { architecture: ArchitectureCard };
const DEFAULT_VIEWPORT: Viewport = { x: 50, y: 75, zoom: 0.9 };

type Props = {
  graph: Graph; scopeId: string; editorId: string; selected: string | null; disabled: boolean; revealId: string | null;
  onSelect: (id: string | null) => void; onOpenStructure: (id: string) => void; onOpenEditor: (id: string) => void;
  onAddNode: (parentId: string) => void; onSector: (areaId: string) => void;
  /** Puštěný prvek; `area` = domovská oblast, která za kartou vyrostla (uloží se s ní jednou změnou). */
  onMove: (id: string, x: number, y: number, area?: Rect & { id: string }) => Promise<void>; onConnect: (source: string, target: string) => void;
  onResize: (id: string, w: number, h: number) => Promise<void>;
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
    resizeArea: (id, w, h) => { void latest.current.onResize(id, w, h).catch(() => setNodes(make())); },
  }), []);
  const make = (): ArchitectureNode[] => graph.nodes.filter((node) => node.parentId === scopeId).map((node) => {
    const area = node.kind === "area";
    return {
      id: node.id, type: "architecture", position: { x: node.x, y: node.y }, selected: node.id === selected,
      zIndex: area ? -1 : 1, style: area ? { width: node.size?.w ?? 720, height: node.size?.h ?? 480 } : { width: CARD_WIDTH },
      data: { node, disabled, actions, summary: area || node.kind === "comment" ? null : cardSummary(node, graph), areaLabel: area ? areaSectorLabel(node, graph) : null },
    };
  });
  const [nodes, setNodes] = useState<ArchitectureNode[]>(make);
  // Rostoucí oblast: tah karty přes hranu natáhne v náhledu jen uzel domovské oblasti (`area-growth.ts`).
  const growth = useAreaGrowth(setNodes);
  const bodies = () => cardBodies(graph, scopeId, new Map(nodes.map((node) => [node.id, node.measured])));
  const nodeSource = useRef({ graph, scopeId });
  const viewportKey = `opora:architecture-viewport:${editorId}:${scopeId}`;
  const [viewport] = useState<Viewport | null>(() => readViewport(viewportKey));
  // UI changes (selection / save lock) must not reset a dragged node to the last saved position.
  // A new graph still supplies authoritative positions; failed moves are restored by onNodeDragStop.
  useEffect(() => {
    const sameSource = nodeSource.current.graph === graph && nodeSource.current.scopeId === scopeId;
    nodeSource.current = { graph, scopeId };
    setNodes((old) => make().map((next) => {
      const prior = old.find((item) => item.id === next.id);
      return { ...next, ...(prior?.measured ? { measured: prior.measured } : {}),
        ...(sameSource && prior ? { position: prior.position } : {}) };
    }));
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
    return { id: edge.id, source: edge.source, target: edge.target, label: look.label, className: look.className, ariaLabel: look.title,
      markerEnd: { type: MarkerType.ArrowClosed, color: look.color, width: 16, height: 16 },
      style: { stroke: look.stroke, strokeWidth: look.width, strokeDasharray: look.dash } };
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
      onNodeDragStart={(_, node) => { if (node.data.node.kind !== "area") growth.begin(node.data.node, graph.nodes, bodies()); }}
      onNodeDrag={(_, node) => growth.preview(node.position.x, node.position.y)}
      onNodeDragStop={(_, node) => {
        const session = growth.finish();
        const stored = graph.nodes.find((item) => item.id === node.id);
        const all = bodies();
        const body = all.find((item) => item.id === node.id);
        // Oblast se táhne dál beze změny; karta buď natáhne domovskou oblast, nebo dosedne jako v editoru (`settleCard`).
        const drop = stored && stored.kind !== "area" && body
          ? dropCard(session, { ...stored, ...node.position }, { ...body, x: body.x + node.position.x - stored.x, y: body.y + node.position.y - stored.y },
            all.filter((item) => item.id !== node.id), graph.nodes.filter((item) => item.parentId === scopeId && item.kind === "area" && !!item.size))
          : { ...node.position };
        if (session) growth.show(session.homeId, "area" in drop && drop.area ? drop.area : session.start);
        void props.onMove(node.id, drop.x, drop.y, "area" in drop ? drop.area : undefined).catch(() => setNodes(make()));
      }}
      onConnect={(connection) => { if (connection.source && connection.target) props.onConnect(connection.source, connection.target); }}
      onMoveEnd={(_, next) => { try { localStorage.setItem(viewportKey, JSON.stringify(next)); } catch { /* Navigation works without storage. */ } }}
      deleteKeyCode={null}>
      <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#294454"/>
      <Controls showInteractive={false}/>
      <PortZoomVar/>
    </ReactFlow>
  </div>;
}
