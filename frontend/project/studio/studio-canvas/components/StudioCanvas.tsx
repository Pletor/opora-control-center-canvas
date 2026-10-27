import { useMemo, type KeyboardEvent } from "react";
import { Background, BackgroundVariant, Controls, MiniMap, ReactFlow, type Node } from "@xyflow/react";
import StudioCard from "../../studio-card/components/StudioCard";
import StudioGroup from "../../studio-card/components/StudioGroup";
import type { StudioCardView } from "../../studio-card/logic/card-view";
import type { StudioLink as Link } from "../../logic/studio-level";
import { flowEdges, flowNodes } from "../logic/canvas-flow";
import { layoutLevel } from "../logic/studio-layout";
import { keyAction, nextInDirection, type StudioKeyAction } from "../logic/studio-keys";
import StudioLink from "./StudioLink";
import "../styles/studio-canvas.css";

const nodeTypes = { "studio-card": StudioCard, "studio-group": StudioGroup };
const edgeTypes = { "studio-link": StudioLink };

type Props = {
  /** Klíč úrovně: změna zanoření plátno znovu napasuje na nové karty. */
  levelKey: string;
  cards: StudioCardView[]; grouped: Set<string>; links: Link[]; selected: string | null;
  onSelect: (id: string | null) => void; onEnter: (id: string) => void; onUp: () => void;
};

/** Plátno jedné úrovně Studia v designu TechViz: tmavé pozadí s mřížkou teček, karty na deterministických polohách,
 * Bézierovy vazby podle `carries`, minimapa vpravo dole, ovladače zoom ± a fit, zoom 0,1–3. Karty se netahají a
 * polohy se neukládají. Klik vybere, dvojklik nebo Enter sestoupí, Backspace vystoupí, šipky posunou výběr, Escape
 * výběr zruší; vše hlásí rodiči. */
export default function StudioCanvas({ levelKey, cards, grouped, links, selected, onSelect, onEnter, onUp }: Props) {
  const layout = useMemo(() => layoutLevel(cards.map((card) => ({ id: card.id, grouped: grouped.has(card.id) })), links), [cards, grouped, links]);
  const nodes = useMemo(() => flowNodes(cards, layout, selected, (view) => ({ view, onEnter })), [cards, layout, selected, onEnter]);
  const edges = useMemo(() => flowEdges(links), [links]);
  const states = useMemo(() => new Map(cards.map((card) => [card.id, card.state])), [cards]);
  function act(action: StudioKeyAction, event: KeyboardEvent) {
    if (!action) return;
    event.preventDefault();
    if (action.kind === "move") onSelect(nextInDirection(cards.map((card) => ({ id: card.id, ...layout.positions.get(card.id)! })), selected, action.direction));
    else if (action.kind === "enter") { if (selected) onEnter(selected); }
    else if (action.kind === "up") onUp();
    else onSelect(null);
  }
  return <div className="studio-canvas" data-testid="studio-canvas" tabIndex={0} aria-label="Plátno Studia: šipky vybírají kartu, Enter sestoupí, Backspace vystoupí"
    onKeyDown={(event) => { if (!(event.target instanceof HTMLInputElement || event.target instanceof HTMLButtonElement)) act(keyAction(event.key), event); }}>
    <ReactFlow key={levelKey} nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} fitView fitViewOptions={{ padding: 0.2, maxZoom: 1 }}
      minZoom={0.1} maxZoom={3} nodesDraggable={false} nodesConnectable={false} elementsSelectable panOnScroll={false} zoomOnDoubleClick={false}
      deleteKeyCode={null} selectionKeyCode={null} multiSelectionKeyCode={null} colorMode="dark"
      onNodeClick={(_, node: Node) => node.type === "studio-card" && onSelect(node.id)} onPaneClick={() => onSelect(null)}>
      <Background variant={BackgroundVariant.Dots} gap={24} size={1.2} color="var(--studio-dot)"/>
      <MiniMap position="bottom-right" pannable zoomable ariaLabel="Minimapa úrovně" className="studio-canvas__minimap"
        nodeColor={(node) => node.type === "studio-group" ? "transparent" : `var(--studio-state-${states.get(node.id) ?? "plan"})`}
        nodeStrokeColor={(node) => node.type === "studio-group" ? "var(--studio-line)" : "transparent"} nodeBorderRadius={6} maskColor="#0b121ecc"/>
      <Controls position="top-right" showInteractive={false} className="studio-canvas__controls" fitViewOptions={{ padding: 0.2, maxZoom: 1 }}/>
    </ReactFlow>
    {!cards.length && <p className="studio-canvas__empty">Tato úroveň zatím nemá žádné karty.</p>}
  </div>;
}
