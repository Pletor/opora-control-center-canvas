import { useEffect, useMemo, useRef, useState } from "react";
import { ReactFlow, Background, BackgroundVariant, Controls, MarkerType, applyNodeChanges, type ReactFlowInstance, type Viewport } from "@xyflow/react";
import type { EdgeCarries, Graph } from "@/shared/types/logic/types";
import { CATALOG_DRAG_TYPE, CATALOG_ITEMS } from "@/editor/component-library/library-catalog/logic/library-catalog";
import type { CatalogLink } from "@/editor/component-library/library-catalog/logic/catalog-plan";
import { areaSectorLabel, cardBodies, cardSummary, CARD_WIDTH, edgeLook } from "../logic/canvas-model";
import { dropCard, type Rect } from "@/editor/canvas/area/logic/area-growth";
import { useAreaGrowth } from "@/editor/canvas/area/logic/use-area-growth";
import { viewportShowsAllNodes } from "../logic/viewport-visibility";
import PortZoomVar from "@/shared/flow-ports/components/PortZoomVar";
import { edgeHintText } from "../edge-hint/logic/edge-hint";
import EdgeHint from "../edge-hint/components/EdgeHint";
import ArchitectureCard, { type ArchitectureNode, type CardActions } from "../map-card/components/ArchitectureCard";
import PortMenu from "../port-menu/components/PortMenu";
import { hasPortMenu, linkTargets } from "../port-menu/logic/port-menu";
import { menuPosition, newCardPosition, planBox, type Box } from "../port-menu/logic/port-menu-place";
import { cardPorts } from "../map-card/logic/card-face";
import { canRemoveEditorEdge } from "../../logic/editor-model";
import ArchitectureLink, { type MapLinkEdge } from "../map-link/components/ArchitectureLink";
import type { MapMotion } from "../map-link/logic/link-motion";
import type { CardState } from "../../card-state/logic/card-state";
import { MotionContext, useParticleAnimator } from "@/project/studio/studio-motion/logic/motion-context";
import { PULSE_CLASS } from "@/project/studio/studio-motion/logic/motion-plan";

const nodeTypes = { architecture: ArchitectureCard };
const edgeTypes = { "map-link": ArchitectureLink };
const DEFAULT_VIEWPORT: Viewport = { x: 50, y: 75, zoom: 0.9 };

type Props = {
  graph: Graph; scopeId: string; editorId: string; selected: string | null; disabled: boolean; revealId: string | null;
  onSelect: (id: string | null) => void; onOpenStructure: (id: string) => void; onOpenEditor: (id: string) => void;
  onAddNode: (parentId: string) => void; onSector: (areaId: string) => void;
  /** Podstránka na plátně (karta-odkaz nebo dvojklik) přepne rozsah editoru na svou stránku. */
  onOpenPage: (pageId: string) => void;
  /** Puštěný prvek; `area` = domovská oblast, která za kartou vyrostla (uloží se s ní jednou změnou). */
  onMove: (id: string, x: number, y: number, area?: Rect & { id: string }) => Promise<void>; onConnect: (source: string, target: string, carries?: EdgeCarries | null) => void;
  onResize: (id: string, w: number, h: number) => Promise<void>;
  /** Popelnice nakreslené vazby (`next` / `flow`); bez zámku ji nabídne jen odemčené plátno. */
  onRemoveEdge: (edgeId: string) => void;
  /** `link` = nabídka vazby z portu: nová karta i vazba ze zdroje vzniknou jedním plánem (`catalogPlan`). */
  onInsert: (id: string, targetId: string | null, point: { x: number; y: number }, link?: CatalogLink) => void;
  /** Skutečný stav od rodiče: stav každé karty (`card-state/`) a pohyb vazeb a pulz karet (`map-link/`). */
  life: { states: ReadonlyMap<string, CardState>; motion: MapMotion };
};
type PortMenuState = { sourceId: string; at: { x: number; y: number }; port: HTMLElement };

/** Stored viewport of this map, or null on the first visit (the map then fits its cards). */
function readViewport(key: string): Viewport | null {
  try {
    const value = JSON.parse(localStorage.getItem(key) ?? "null");
    return value && [value.x, value.y, value.zoom].every(Number.isFinite) ? value : null;
  } catch { return null; }
}

/** Map of one page: areas, sectors and nodes of the open scope, with links between them. */
export default function ArchitectureCanvas(props: Props) {
  const { graph, scopeId, editorId, selected, disabled, revealId, life } = props;
  const animator = useParticleAnimator();
  const flow = useRef<ReactFlowInstance<ArchitectureNode, MapLinkEdge> | null>(null);
  const stage = useRef<HTMLDivElement | null>(null);
  const [hovered, setHovered] = useState<{ edgeId: string; x: number; y: number } | null>(null);
  const [menu, setMenu] = useState<PortMenuState | null>(null);
  const latest = useRef(props); latest.current = props;
  const actions = useMemo<CardActions>(() => ({
    select: (id) => latest.current.onSelect(id), openStructure: (id) => latest.current.onOpenStructure(id),
    openEditor: (id) => latest.current.onOpenEditor(id), addNode: (id) => latest.current.onAddNode(id), addSector: (id) => latest.current.onSector(id),
    openPage: (id) => latest.current.onOpenPage(id),
    resizeArea: (id, w, h) => { void latest.current.onResize(id, w, h).catch(() => setNodes(make())); },
    openPortMenu: (sourceId, port) => {
      const box = stage.current?.getBoundingClientRect(); const card = port.closest(".react-flow__node")?.getBoundingClientRect();
      if (!box || !card) return;
      const rel = (rect: DOMRect): Box => ({ x: rect.left - box.left, y: rect.top - box.top, w: rect.width, h: rect.height });
      setMenu({ sourceId, port, at: menuPosition(rel(port.getBoundingClientRect()), rel(card), { w: box.width, h: box.height }) });
    },
  }), []);
  const make = (): ArchitectureNode[] => graph.nodes.filter((node) => node.parentId === scopeId).map((node) => {
    const area = node.kind === "area";
    return {
      id: node.id, type: "architecture", position: { x: node.x, y: node.y }, selected: node.id === selected, className: life.motion.pulsing.has(node.id) ? PULSE_CLASS : undefined,
      zIndex: area ? -1 : 1, style: area ? { width: node.size?.w ?? 720, height: node.size?.h ?? 480 } : { width: CARD_WIDTH },
      data: { node, disabled, actions, summary: area || node.kind === "comment" ? null : cardSummary(node, graph), areaLabel: area ? areaSectorLabel(node, graph) : null,
        state: life.states.get(node.id) ?? null, ports: cardPorts(graph.edges, node.id) },
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
  }, [graph, scopeId, selected, disabled, life.states, life.motion.pulsing]);
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
  const removeEdge = (edgeId: string) => { setHovered(null); latest.current.onRemoveEdge(edgeId); };
  const ids = new Set(nodes.map((node) => node.id));
  const edges: MapLinkEdge[] = graph.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target)).map((edge) => {
    const look = edgeLook(edge, graph);
    return { id: edge.id, source: edge.source, target: edge.target, type: "map-link", label: look.label, className: look.className, ariaLabel: look.title,
      data: { tone: look.stroke, motion: life.motion.links.get(edge.id), onRemove: !disabled && canRemoveEditorEdge(edge) ? removeEdge : undefined },
      markerEnd: { type: MarkerType.ArrowClosed, color: look.color, width: 14, height: 14 },
      style: { stroke: look.stroke, strokeWidth: look.width, strokeDasharray: look.dash } };
  });
  const hoverAt = (event: { clientX: number; clientY: number }, edgeId: string) => {
    const box = stage.current?.getBoundingClientRect();
    if (box) setHovered({ edgeId, x: event.clientX - box.left, y: event.clientY - box.top });
  };
  const hoveredEdge = hovered ? graph.edges.find((edge) => edge.id === hovered.edgeId) : undefined;
  const menuSource = menu && !disabled ? graph.nodes.find((node) => node.id === menu.sourceId && node.parentId === scopeId && hasPortMenu(node)) : undefined;
  /** Zavření vrátí fokus na port, ze kterého nabídka vyjela (klávesnice pokračuje tam, kde byla). */
  const closeMenu = () => { if (menu?.port.isConnected) menu.port.focus(); setMenu(null); };
  return <div className="page-editor__canvas" data-testid="architecture-canvas" ref={stage}
    onDragOver={(event) => { if (!disabled && event.dataTransfer.types.includes(CATALOG_DRAG_TYPE)) { event.preventDefault(); event.dataTransfer.dropEffect = "copy"; } }}
    onDrop={(event) => {
      if (disabled || !event.dataTransfer.types.includes(CATALOG_DRAG_TYPE) || !flow.current) return;
      event.preventDefault();
      const target = event.target instanceof Element ? event.target.closest(".react-flow__node")?.getAttribute("data-id") ?? null : null;
      const point = flow.current.screenToFlowPosition({ x: event.clientX, y: event.clientY });
      props.onInsert(event.dataTransfer.getData(CATALOG_DRAG_TYPE), target, { x: point.x - 135, y: point.y - 45 });
    }}>
    <MotionContext.Provider value={animator}>
    <ReactFlow<ArchitectureNode, MapLinkEdge> nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} colorMode="dark"
      onInit={(instance) => {
        flow.current = instance;
        // A stored viewport that shows no card (cards moved or window resized) is dropped in favour of fitting the map.
        if (!viewport || !stage.current) return;
        const size = { width: stage.current.clientWidth, height: stage.current.clientHeight };
        const boxes = latest.current.graph.nodes.filter((node) => node.parentId === scopeId).map((node) => ({ x: node.x, y: node.y, w: node.kind === "area" ? node.size?.w ?? 720 : 270, h: node.kind === "area" ? node.size?.h ?? 480 : 90 }));
        if (!viewportShowsAllNodes(viewport, size, boxes)) requestAnimationFrame(() => { void instance.fitView({ maxZoom: 1, padding: 0.15 }); });
      }} defaultViewport={viewport ?? DEFAULT_VIEWPORT} fitView={!viewport} fitViewOptions={{ maxZoom: 1, padding: 0.15 }} minZoom={0.2} maxZoom={1.6} elevateNodesOnSelect={false}
      onNodesChange={(changes) => setNodes((old) => applyNodeChanges(changes, old))} nodesDraggable={!disabled} nodesConnectable={!disabled}
      onEdgeMouseEnter={(event, edge) => hoverAt(event, edge.id)} onEdgeMouseMove={(event, edge) => hoverAt(event, edge.id)} onEdgeMouseLeave={() => setHovered(null)}
      onNodeClick={(_, node) => props.onSelect(node.id)} onPaneClick={() => props.onSelect(null)}
      onNodeDoubleClick={(_, node) => { const card = node.data.node; if (card.site?.kind === "page") props.onOpenPage(node.id); else if (card.kind === "node" || card.kind === "sector") props.onOpenStructure(node.id); }}
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
      onMoveStart={() => setMenu(null)} onMoveEnd={(_, next) => { try { localStorage.setItem(viewportKey, JSON.stringify(next)); } catch { /* Navigation works without storage. */ } }}
      deleteKeyCode={null}>
      <Background variant={BackgroundVariant.Dots} gap={24} size={1.2} color="var(--studio-dot)"/>
      <Controls showInteractive={false}/>
      <PortZoomVar/>
    </ReactFlow>
    </MotionContext.Provider>
    {menu && menuSource ? <PortMenu key={menu.sourceId} sourceName={menuSource.name} at={menu.at} targets={linkTargets(graph, scopeId, menuSource.id)} items={CATALOG_ITEMS}
      onClose={closeMenu} onLink={(target, carries) => { closeMenu(); props.onConnect(menuSource.id, target, carries); }}
      onCreate={(itemId) => {
        closeMenu(); const layer = graph.nodes.filter((node) => node.parentId === scopeId).map(planBox);
        props.onInsert(itemId, null, newCardPosition(menuSource, layer), { nodeId: menuSource.id, side: "source" });
      }}/> : null}
    {hovered && hoveredEdge ? <EdgeHint hint={edgeHintText(hoveredEdge, graph)} x={hovered.x} y={hovered.y}/> : null}
  </div>;
}
