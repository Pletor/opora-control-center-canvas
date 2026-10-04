import { useEffect, useState, type ReactNode } from "react";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { activePageId, projectTree } from "../project-tree/logic/project-tree-model";
import { scopePath } from "../logic/canvas-model";
import { pageLayoutClass, type PageFocus } from "../logic/page-layout";
import PageSidebar from "./PageSidebar";
import ArchitectureCanvas from "./ArchitectureCanvas";
import PageIcon from "./PageIcon";
import "../styles/page-editor.css";

type Props = {
  graph: Graph; domain: CanvasNode; scope: CanvasNode; projectName: string; selectedId: string | null;
  editorId: string; disabled: boolean; reveal: string | null;
  /** Hierarchical editor and element detail are composed by the parent and dropped into their columns. */
  structure: ReactNode | null; detail: ReactNode | null;
  onOpenPage: (domainId: string, pageId: string) => void; onAddPage: (domainId: string) => void; onOpenScope: (id: string) => void;
  onSelect: (id: string | null) => void; onOpenStructure: (id: string) => void; onOpenEditor: (id: string) => void;
  onInsert: (id: string, target?: string | null, point?: { x: number; y: number }) => void;
  onMove: (id: string, x: number, y: number) => Promise<void>; onConnect: (source: string, target: string) => void;
  onSector: (parentId: string) => void; onArea: () => void; onAddNode: (parentId: string) => void;
};

/** Page editor: tree/library | architecture map | hierarchical editor | element detail. */
export default function PageEditor(props: Props) {
  const { graph, domain, scope, selectedId, disabled, structure, detail } = props;
  const [focus, setFocus] = useState<PageFocus>("map");
  useEffect(() => setFocus(structure ? "structure" : "map"), [!!structure]);
  const groups = projectTree(graph, domain.id, activePageId(graph, scope.id));
  const path = scopePath(graph, scope.id, domain.id);
  const empty = !graph.nodes.some((node) => node.parentId === scope.id);
  const toggle = <div className="page-editor__switch" role="group" aria-label="Co zobrazit">
    <button type="button" className="page-editor__switch-button" aria-pressed={focus === "map"} onClick={() => setFocus("map")}>Mapa</button>
    <button type="button" className="page-editor__switch-button" aria-pressed={focus === "structure"} onClick={() => setFocus("structure")}>Struktura</button>
  </div>;
  return <div className={pageLayoutClass({ structure: !!structure, detail: !!detail, focus })} data-testid="architecture-page-editor">
    <PageSidebar projectName={props.projectName} groups={groups} scopeName={scope.name} disabled={disabled}
      onOpenPage={props.onOpenPage} onAddPage={props.onAddPage} onInsert={(id) => props.onInsert(id)}/>
    <main className="page-editor__map" aria-label="Mapa architektury">
      <header className="page-editor__map-head">
        <PageIcon name="area" size={22} className="page-editor__map-icon"/>
        <div className="page-editor__map-text">
          <h2 className="page-editor__map-title">Mapa architektury — {scope.name}</h2>
          <p className="page-editor__map-lead">Přehled komponent a jejich propojení na stránce</p>
        </div>
        {structure && toggle}
      </header>
      {path.length > 1 && <nav className="page-editor__crumbs" aria-label="Cesta mapou">
        {path.map((node, index) => <button key={node.id} type="button" className="page-editor__crumb" aria-current={index === path.length - 1 ? "page" : undefined}
          onClick={() => props.onOpenScope(node.id)}>{node.name}</button>)}
      </nav>}
      <div className="page-editor__stage">
        <ArchitectureCanvas key={props.editorId + ":" + scope.id} graph={graph} scopeId={scope.id} editorId={props.editorId} selected={selectedId}
          disabled={disabled} revealId={props.reveal} onSelect={props.onSelect} onOpenStructure={props.onOpenStructure} onOpenEditor={props.onOpenEditor}
          onAddNode={props.onAddNode} onSector={props.onSector} onMove={props.onMove} onConnect={props.onConnect}
          onInsert={(id, target, point) => props.onInsert(id, target, point)}/>
        {empty && <div className="page-editor__empty">
          <h3 className="page-editor__empty-title">{scope.name}</h3>
          <p className="page-editor__empty-text">Prázdná mapa této stránky. Začněte oblastí nebo přetáhněte prvek z Knihovny.</p>
          <button type="button" className="page-editor__empty-button" disabled={disabled} onClick={props.onArea}>+ Přidat oblast</button>
        </div>}
      </div>
    </main>
    {structure && <section className="page-editor__structure"><div className="page-editor__structure-bar">{toggle}</div>{structure}</section>}
    {detail && <aside className="page-editor__detail" aria-label="Detail prvku">{detail}</aside>}
  </div>;
}
