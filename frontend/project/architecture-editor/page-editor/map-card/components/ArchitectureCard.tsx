import { useRef } from "react";
import { Position, type Node, type NodeProps } from "@xyflow/react";
import type { CanvasNode } from "@/shared/types/logic/types";
import type { CardSummary } from "../../logic/canvas-model";
import type { CardPorts } from "../logic/card-face";
import { cardFace } from "../logic/card-face";
import type { CardState } from "../../../card-state/logic/card-state";
import { holesLabel } from "../../../card-state/logic/card-state";
import CardIcon from "../../../card-state/components/CardIcon";
import CardStateChip from "../../../card-state/components/CardStateChip";
import CardMenu from "./CardMenu";
import CardStages from "./CardStages";
import AreaFrame from "./AreaFrame";
import PortHandle from "@/shared/flow-ports/components/PortHandle";
import { isPortClick } from "../../port-menu/logic/port-menu-place";
import "../styles/map-card.css";

/** Stable callbacks shared by all cards; the canvas routes them to the newest parent handlers. */
export type CardActions = {
  select: (id: string) => void; openStructure: (id: string) => void; openEditor: (id: string) => void;
  addNode: (parentId: string) => void; addSector: (areaId: string) => void;
  /** Podstránka na plátně je odkaz: přepne rozsah editoru na svou stránku (stejně jako strom a pruh navigace). */
  openPage: (pageId: string) => void;
  /** Ustálený rozměr rámečku po tažení tahadla oblasti. */
  resizeArea: (areaId: string, w: number, h: number) => void;
  /** Klik nebo Enter na výstupním portu: nabídka vazby u tohoto úchytu (`port-menu/`). */
  openPortMenu: (sourceId: string, port: HTMLElement) => void;
};
export type CardData = {
  node: CanvasNode; summary: CardSummary | null; areaLabel: string | null; disabled: boolean; actions: CardActions;
  /** Stav karty jako ve Studiu (`card-state/`); null = Studio kartu nezná nebo fakta ještě nejsou. */
  state: CardState | null;
  /** Druh toku vazeb na vstupu a výstupu (barva portů); null = volný port. */
  ports: CardPorts;
};
export type ArchitectureNode = Node<CardData>;

/** Karta mapy v designu Studia: hlavička s ikonou druhu, názvem, štítkem stavu a menu ⋮, druh s adresou, účel, až tři
 * potomci jako buňky stupňů a pata se souhrnem, dírami a akcemi. Rám nese barvu stavu (staví se = dýchá), ikona
 * barvu vrstvy. Porty jsou body na obvodu v barvě `carries`; výstupní port: klik nebo Enter = nabídka vazby, tah = vazba. */
export default function ArchitectureCard({ data, selected }: NodeProps<ArchitectureNode>) {
  const { node, summary, actions, state } = data;
  /** Kde stisk výstupního portu začal: puštění blíž než práh je klik (nabídka), dál tah vazby. */
  const down = useRef<{ x: number; y: number } | null>(null);
  if (node.kind === "area") return <AreaFrame data={data} selected={selected}/>;
  if (node.kind === "comment" || !summary) return <article className="map-card map-card--comment" data-testid={"architecture-card-" + node.id}>
    <p className="map-card__purpose">{node.name}</p></article>;
  const page = summary.page;
  const face = cardFace(node);
  const tone = state ? ` card-state--${state.state}${state.state === "building" ? " card-state__frame--building" : ""}` : "";
  return <article className={`map-card map-card--${summary.tone}${page ? " map-card--page" : ""}${selected ? " map-card--selected" : ""}${tone}`}
    data-testid={"architecture-card-" + node.id} data-state={state?.state}>
    <PortHandle kind="next" type="target" position={Position.Left} className={"map-card__port map-card__port--" + (data.ports.in ?? "open")}/>
    <PortHandle kind="next" type="source" position={Position.Right} className={"map-card__port map-card__port--" + (data.ports.out ?? "open")} hint="klik: nabídka vazby, tah: propojit" aria-haspopup="dialog"
      onPointerDown={(event) => { down.current = { x: event.clientX, y: event.clientY }; }}
      onClick={(event) => { event.stopPropagation(); const click = isPortClick(down.current, { x: event.clientX, y: event.clientY }); down.current = null; if (click && !data.disabled) actions.openPortMenu(node.id, event.currentTarget); }}
      onKeyDown={(event) => { if (event.key !== "Enter" && event.key !== " ") return; event.preventDefault(); event.stopPropagation(); if (!data.disabled) actions.openPortMenu(node.id, event.currentTarget); }}/>
    <header className="map-card__head">
      <CardIcon node={node} className="map-card__icon"/>
      <strong className="map-card__title" title={node.name}>{node.name}</strong>
      <CardStateChip state={state} testId={"architecture-state-" + node.id}/>
      <CardMenu name={node.name} items={[
        { label: "Otevřít detail", testId: "architecture-menu-structure-" + node.id, onClick: () => actions.openStructure(node.id) },
        { label: "Otevřít v Editoru", testId: "architecture-menu-editor-" + node.id, onClick: () => actions.openEditor(node.id) },
      ]}/>
    </header>
    <div className="map-card__body">
      <span className="map-card__kind">{face.kind}{face.subtitle && <code className="map-card__subtitle">{face.subtitle}</code>}</span>
      {node.purpose && <p className="map-card__purpose">{node.purpose}</p>}
    </div>
    <CardStages preview={summary.preview} more={summary.more} actions={actions}/>
    <footer className="map-card__foot">
      <span className="map-card__summary" title={state?.summary}>{summary.countLabel}{state && state.summary !== "bez dětí" ? ` · ${state.summary}` : ""}</span>
      {state && state.holes > 0 && <span className="map-card__holes" title="Díry mapy pod touto kartou">{holesLabel(state.holes)}</span>}
      {page ? <button type="button" className="map-card__action map-card__action--page nodrag" data-testid={"architecture-open-page-" + node.id}
        aria-label={`Otevřít stránku ${node.name} v Editoru stránky`} onClick={(event) => { event.stopPropagation(); actions.openPage(node.id); }}>Otevřít stránku →</button>
      : <>
        <button type="button" className="map-card__action nodrag" disabled={data.disabled} data-testid={"architecture-add-node-" + node.id}
          aria-label={`Přidat komponentu do ${node.name}`} onClick={(event) => { event.stopPropagation(); actions.addNode(node.id); }}>+ Komponenta</button>
        <button type="button" className="map-card__action map-card__action--open nodrag" data-testid={"architecture-open-structure-" + node.id}
          onClick={(event) => { event.stopPropagation(); actions.openStructure(node.id); }}>Detail ↗</button>
      </>}
    </footer>
  </article>;
}
