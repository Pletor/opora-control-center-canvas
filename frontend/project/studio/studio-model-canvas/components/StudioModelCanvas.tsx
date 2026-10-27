import { useCallback, useMemo, useState, type DragEvent, type PointerEvent } from "react";
import { Background, BackgroundVariant, Controls, MiniMap, ReactFlow, ReactFlowProvider, useReactFlow, type NodeChange } from "@xyflow/react";
import type { Point } from "../../model/logic/model-types";
import type { EditModel, Selection } from "../../studio-model/logic/model-edit";
import type { BindingCard } from "../../studio-layer/logic/studio-layer";
import { PALETTE_DRAG_TYPE } from "../../studio-model-palette/logic/palette-groups";
import { modelCards, modelFlowNodes, modelLayout, modelLinks } from "../logic/model-flow";
import { orient, portKey, portTargets, type Link, type PendingPort } from "../logic/connect-gesture";
import { useConnectDrag } from "../logic/use-connect-drag";
import { CardActionsContext } from "../logic/card-actions";
import type { RunFrame } from "../../studio-model-run/logic/flow-animator";
import { FlowAnimatorContext, useFlowAnimator } from "../../studio-model-run/logic/flow-context";
import type { CardRun, LinkFlow } from "../../studio-model-run/logic/run-view";
import ModelCard from "./ModelCard";
import ModelLinks from "./ModelLinks";
import "../styles/studio-model-canvas.css";

const nodeTypes = { "model-card": ModelCard };

type Props = {
  model: EditModel; bindings: ReadonlyMap<string, BindingCard>; selection: Selection; pending: PendingPort | null;
  onSelect: (selection: Selection) => void; onMove: (id: string, position: Point) => void; onAdd: (typeId: string, position: Point) => void;
  onPortClick: (port: PendingPort) => void; onLink: (link: Link) => void; onMessage: (text: string) => void;
  /** Běh MODELu: snímek pro hodiny částic, vypočtené karty a toky vazeb (prázdné, když běh nezačal). */
  frame: RunFrame; runs: ReadonlyMap<string, CardRun>; flows: ReadonlyMap<string, LinkFlow>;
};

/** Plátno vrstvy MODEL: stejné ovládání jako Skutečnost (zoom 0,1–3, fit, minimapa, posun pozadí), ale fialovější noc
 * a trvalý štítek „MODEL – výpočet, ne měření“. Karty se dají táhnout (poloha jde do modelu po puštění), porty
 * propojovat klikem nebo tahem, komponenty z katalogu pouštět na místo. Za běhu nesou karty vypočtená čísla a po
 * vazbách jedou částice (jeden animátor plátna řízený snímkem běhu; Pause plátno zmrazí). Všechno hlásí rodiči;
 * nic neukládá. */
export default function StudioModelCanvas(props: Props) {
  return <ReactFlowProvider><ModelFlow {...props}/></ReactFlowProvider>;
}

function ModelFlow({ model, bindings, selection, pending, onSelect, onMove, onAdd, onPortClick, onLink, onMessage, frame, runs, flows }: Props) {
  const flow = useReactFlow();
  const animator = useFlowAnimator(frame);
  const [moving, setMoving] = useState<Map<string, Point>>(() => new Map());
  const toFlow = useCallback((point: Point) => flow.screenToFlowPosition(point), [flow]);
  const { drag, begin } = useConnectDrag(toFlow, {
    onClick: onPortClick,
    onDrop: (start, target) => {
      const link = target && orient(start, target);
      if (link) onLink(link); else onMessage(target ? "Vazba musí vést z výstupu na vstup." : "Vazba nebyla vytvořena: pusťte úchyt na kompatibilním portu.");
    },
  });
  const start = drag?.start ?? pending;
  const targets = useMemo(() => portTargets(model, start), [model, start]);
  const layout = useMemo(() => modelLayout(model, moving), [model, moving]);
  const cards = useMemo(() => modelCards(model, layout, { pending: start ? portKey(start) : null, targets, bindings, runs }), [model, layout, start, targets, bindings, runs]);
  const nodes = useMemo(() => modelFlowNodes(cards, layout, selection), [cards, layout, selection]);
  const links = useMemo(() => modelLinks(model, layout, selection), [model, layout, selection]);
  const portOf = (nodeId: string, portId: string) => {
    const index = cards.findIndex((card) => card.id === nodeId), port = cards[index]?.ports.find((item) => item.id === portId);
    return port ? { port, at: { x: layout.nodes[index].x + port.x, y: layout.nodes[index].y + port.y } } : null;
  };
  const actions = {
    onPortDown: (nodeId: string, portId: string, event: PointerEvent) => {
      const found = portOf(nodeId, portId);
      if (found) begin({ nodeId, portId, direction: found.port.direction }, found.at, event);
    },
    onPortKey: (nodeId: string, portId: string) => {
      const found = portOf(nodeId, portId);
      if (found) onPortClick({ nodeId, portId, direction: found.port.direction });
    },
  };
  const onNodesChange = (changes: NodeChange[]) => {
    const next = new Map(moving);
    for (const change of changes) if (change.type === "position" && change.position && change.dragging) next.set(change.id, change.position);
    if (next.size !== moving.size || [...next].some(([id, at]) => moving.get(id) !== at)) setMoving(next);
  };
  const drop = (event: DragEvent) => {
    const typeId = event.dataTransfer.getData(PALETTE_DRAG_TYPE);
    if (!typeId) return;
    event.preventDefault();
    onAdd(typeId, toFlow({ x: event.clientX, y: event.clientY }));
  };
  const dragColor = drag ? cards.find((card) => card.id === drag.start.nodeId)?.ports.find((port) => port.id === drag.start.portId)?.color ?? "#fff" : "#fff";
  return <div className={"studio-model-canvas" + (frame.running ? "" : " studio-model-canvas--paused")} data-testid="studio-model-canvas" data-run-tick={frame.tick}
    onDragOver={(event) => { if (event.dataTransfer.types.includes(PALETTE_DRAG_TYPE)) { event.preventDefault(); event.dataTransfer.dropEffect = "copy"; } }} onDrop={drop}>
    <FlowAnimatorContext.Provider value={animator}><CardActionsContext.Provider value={actions}>
      <ReactFlow nodes={nodes} edges={[]} nodeTypes={nodeTypes} onNodesChange={onNodesChange} fitView fitViewOptions={{ padding: 0.2, maxZoom: 1 }}
        minZoom={0.1} maxZoom={3} nodesConnectable={false} elementsSelectable panOnScroll={false} zoomOnDoubleClick={false}
        deleteKeyCode={null} selectionKeyCode={null} multiSelectionKeyCode={null} colorMode="dark"
        onNodeClick={(_, node) => onSelect({ kind: "node", id: node.id })} onPaneClick={() => onSelect(null)}
        onNodeDragStop={(_, node) => { onMove(node.id, node.position); setMoving(new Map()); }}>
        <Background variant={BackgroundVariant.Dots} gap={24} size={1.2} color="var(--studio-model-dot)"/>
        <ModelLinks links={links} flows={flows} drag={drag} dragColor={dragColor} onSelect={(id) => onSelect({ kind: "edge", id })}/>
        <MiniMap position="bottom-right" pannable zoomable ariaLabel="Minimapa modelu" className="studio-model-canvas__minimap"
          nodeColor={() => "var(--studio-model-accent)"} nodeBorderRadius={6} maskColor="#100e1fcc"/>
        <Controls position="top-right" showInteractive={false} className="studio-model-canvas__controls" fitViewOptions={{ padding: 0.2, maxZoom: 1 }}/>
      </ReactFlow>
    </CardActionsContext.Provider></FlowAnimatorContext.Provider>
    <span className="studio-model-canvas__label" data-testid="studio-model-label" title="Vrstva MODEL: čísla jsou výpočet modelu, ne měření projektu">MODEL – výpočet, ne měření</span>
    {!model.nodes.length && <p className="studio-model-canvas__empty">Model je prázdný: přidejte komponentu z katalogu vlevo.</p>}
  </div>;
}
