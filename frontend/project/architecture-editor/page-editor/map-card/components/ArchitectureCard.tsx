import { useRef } from "react";
import { NodeResizer, Position, type Node, type NodeProps } from "@xyflow/react";
import type { CanvasNode } from "@/shared/types/logic/types";
import { AREA_SIZE_MAX, AREA_SIZE_MIN } from "@/editor/canvas/area/logic/area-model";
import { toneOf, type CardSummary } from "../../logic/canvas-model";
import CardMenu from "./CardMenu";
import PortHandle from "@/shared/flow-ports/components/PortHandle";
import PageIcon from "../../components/PageIcon";
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
export type CardData = { node: CanvasNode; summary: CardSummary | null; areaLabel: string | null; disabled: boolean; actions: CardActions };
export type ArchitectureNode = Node<CardData>;

function AreaFrame({ data, selected }: { data: CardData; selected: boolean }) {
  const { node, actions } = data;
  return <article className={"map-card map-card--area" + (selected ? " map-card--selected" : "")} data-testid={"architecture-card-" + node.id}>
    <NodeResizer isVisible={selected && !data.disabled} minWidth={AREA_SIZE_MIN} minHeight={AREA_SIZE_MIN} maxWidth={AREA_SIZE_MAX} maxHeight={AREA_SIZE_MAX}
      lineClassName="map-card__resize-line" handleClassName="map-card__resize-handle"
      onResizeEnd={(_, params) => actions.resizeArea(node.id, params.width, params.height)}/>
    <PortHandle kind="flow" type="target" position={Position.Left} className="map-card__port"/>
    <PortHandle kind="flow" type="source" position={Position.Right} className="map-card__port"/>
    <header className="map-card__head">
      <PageIcon name="area" className="map-card__icon"/>
      <strong className="map-card__title">OBLAST: {node.name}</strong>
      <span className="map-card__count">{data.areaLabel}</span>
      <button type="button" className="map-card__area-add nodrag" disabled={data.disabled} data-testid={"architecture-area-sector-" + node.id}
        aria-label={`Přidat sektor do oblasti ${node.name}`} onClick={() => actions.addSector(node.id)}>+ Sektor</button>
    </header>
    {node.purpose && <p className="map-card__purpose">{node.purpose}</p>}
  </article>;
}

/** One map card: area frame, comment note, or sector/node card colored by its layer. */
export default function ArchitectureCard({ data, selected }: NodeProps<ArchitectureNode>) {
  const { node, summary, actions } = data;
  /** Kde stisk výstupního portu začal: puštění blíž než práh je klik (nabídka), dál tah vazby. */
  const down = useRef<{ x: number; y: number } | null>(null);
  if (node.kind === "area") return <AreaFrame data={data} selected={selected}/>;
  if (node.kind === "comment" || !summary) return <article className="map-card map-card--comment" data-testid={"architecture-card-" + node.id}>
    <p className="map-card__purpose">{node.name}</p></article>;
  const sector = node.kind === "sector";
  const page = summary.page;
  return <article className={`map-card map-card--${summary.tone}${page ? " map-card--page" : ""}${selected ? " map-card--selected" : ""}`} data-testid={"architecture-card-" + node.id}>
    <PortHandle kind="next" type="target" position={Position.Left} className="map-card__port"/>
    <PortHandle kind="next" type="source" position={Position.Right} className="map-card__port" hint="klik: nabídka vazby, tah: propojit" aria-haspopup="dialog"
      onPointerDown={(event) => { down.current = { x: event.clientX, y: event.clientY }; }}
      onClick={(event) => { event.stopPropagation(); const click = isPortClick(down.current, { x: event.clientX, y: event.clientY }); down.current = null; if (click && !data.disabled) actions.openPortMenu(node.id, event.currentTarget); }}
      onKeyDown={(event) => { if (event.key !== "Enter" && event.key !== " ") return; event.preventDefault(); event.stopPropagation(); if (!data.disabled) actions.openPortMenu(node.id, event.currentTarget); }}/>
    <header className="map-card__head">
      <span className="map-card__icon"><PageIcon name={summary.tone}/></span>
      <span className="map-card__heading">
        <span className="map-card__kind">{page ? "Podstránka" : sector ? "Sektor" : "Uzel"}</span>
        <strong className="map-card__title">{node.name}</strong>
        {page?.path && <span className="map-card__path">{page.path}</span>}
      </span>
      <span className="map-card__count">{summary.countLabel}</span>
      <CardMenu name={node.name} items={[
        { label: "Otevřít detail", testId: "architecture-menu-structure-" + node.id, onClick: () => actions.openStructure(node.id) },
        { label: "Otevřít v Editoru", testId: "architecture-menu-editor-" + node.id, onClick: () => actions.openEditor(node.id) },
      ]}/>
    </header>
    {node.purpose && <p className="map-card__purpose">{node.purpose}</p>}
    {summary.preview.length > 0 && <ul className="map-card__children">
      {summary.preview.map((child) => <li key={child.id}>
        <button type="button" className={`map-card__child map-card__child--${toneOf(child)} nodrag`} data-testid={"architecture-child-" + child.id}
          onClick={(event) => { event.stopPropagation(); actions.select(child.id); }}
          onDoubleClick={(event) => { event.stopPropagation(); actions.openStructure(child.id); }}>
          <PageIcon name={toneOf(child)} size={15} className="map-card__child-icon"/>
          <span className="map-card__child-name">{child.name}</span>
          {child.purpose && <span className="map-card__child-purpose">{child.purpose}</span>}
        </button>
      </li>)}
      {summary.more > 0 && <li className="map-card__more">+ {summary.more} dalších</li>}
    </ul>}
    {page ? <footer className="map-card__foot">
      <button type="button" className="map-card__open map-card__open--page nodrag" data-testid={"architecture-open-page-" + node.id}
        aria-label={`Otevřít stránku ${node.name} v Editoru stránky`} onClick={(event) => { event.stopPropagation(); actions.openPage(node.id); }}>Otevřít stránku →</button>
    </footer> : <footer className="map-card__foot">
      <button type="button" className="map-card__add nodrag" disabled={data.disabled} data-testid={"architecture-add-node-" + node.id}
        aria-label={`Přidat komponentu do ${node.name}`} onClick={(event) => { event.stopPropagation(); actions.addNode(node.id); }}>+ Přidat komponentu</button>
      <button type="button" className="map-card__open nodrag" data-testid={"architecture-open-structure-" + node.id}
        onClick={(event) => { event.stopPropagation(); actions.openStructure(node.id); }}>Otevřít detail ↗</button>
    </footer>}
  </article>;
}
