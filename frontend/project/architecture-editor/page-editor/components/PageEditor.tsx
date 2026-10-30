import { useEffect, useState, type ReactNode } from "react";
import type { CanvasNode, EdgeCarries, Graph } from "@/shared/types/logic/types";
import type { CatalogLink } from "@/editor/component-library/library-catalog/logic/catalog-plan";
import { activePageId, projectTree } from "../project-tree/logic/project-tree-model";
import { scopePath } from "../logic/canvas-model";
import { pageLayoutClass, type PageFocus } from "../logic/page-layout";
import PageSidebar from "./PageSidebar";
import ArchitectureCanvas from "./ArchitectureCanvas";
import PageIcon from "./PageIcon";
import PageNav from "../page-nav/components/PageNav";
import { pageNav } from "../page-nav/logic/page-nav";
import JourneySlice from "../journey-slice/components/JourneySlice";
import { pageSlices, sectionChips } from "../journey-slice/logic/page-slice";
import { domainPageTree } from "../../logic/domain-model";
import { derivedForDomain, type DerivedJourney } from "../../domain-map/logic/derived-journeys";
import { useMapMotion } from "../map-link/logic/use-map-motion";
import type { CardLife } from "../../card-state/logic/card-state";
import PageDecomposeCopy from "../page-decompose/components/PageDecomposeCopy";
import type { PageDecompose } from "../page-decompose/logic/page-decompose-prompt";
import "../styles/page-editor.css";

type Props = {
  graph: Graph; domain: CanvasNode; scope: CanvasNode; projectName: string; selectedId: string | null;
  /** `disabled` = page content (inserts, moves, links); `structureDisabled` = page structure (+ Stránka in the tree), writable even on main. */
  editorId: string; disabled: boolean; structureDisabled?: boolean; reveal: string | null;
  /** Hierarchical editor and element detail are composed by the parent and dropped into their columns. */
  structure: ReactNode | null; detail: ReactNode | null;
  /** Web state badge of the domain host in the map header (docs/domeny-a-worktree.md §10.3). */
  webBadge?: ReactNode;
  /** Odvozené přechody cest zákazníka (backend §6) pro úsek cesty; null = nenačteno. */
  derivedJourneys?: DerivedJourney[] | null;
  /** Skutečný stav karet (Studio) a cesty pro pohyb vazeb; počítá rodič (`useCardLife`). */
  cards: CardLife;
  /** Zadání rozkladu aktivní stránky pro agenta (docs/architektura-pro-agenty.md §5.2); skládá rodič. */
  decompose?: PageDecompose;
  /** Úsek cesty: „Upravit cestu“ (id) nebo výzva u stránky mimo cesty (`null`) otevře Mapu domény. */
  onOpenJourneys: (journeyId: string | null) => void;
  onOpenPage: (domainId: string, pageId: string) => void; onAddPage: (domainId: string) => void; onOpenScope: (id: string) => void;
  onSelect: (id: string | null) => void; onOpenStructure: (id: string) => void; onOpenEditor: (id: string) => void;
  /** `link` = nabídka vazby z portu: karta i vazba ze zdroje jedním plánem. */
  onInsert: (id: string, target?: string | null, point?: { x: number; y: number }, link?: CatalogLink) => void;
  /** `area` = domovská oblast, která za puštěnou kartou vyrostla; ukládá se s kartou jednou změnou. */
  onMove: (id: string, x: number, y: number, area?: { id: string; x: number; y: number; w: number; h: number }) => Promise<void>; onConnect: (source: string, target: string, carries?: EdgeCarries | null) => void;
  onResize: (id: string, w: number, h: number) => Promise<void>;
  /** Popelnice na nakreslené vazbě plátna: odstraní ji rodič (náhled a potvrzení bez dialogu). */
  onRemoveEdge: (edgeId: string) => void;
  onSector: (parentId: string) => void; onArea: () => void; onAddNode: (parentId: string) => void;
};

/** Page editor: tree/library | architecture map | hierarchical editor | element detail. */
export default function PageEditor(props: Props) {
  const { graph, domain, scope, selectedId, disabled, structure, detail } = props;
  const [focus, setFocus] = useState<PageFocus>("map");
  useEffect(() => setFocus(structure ? "structure" : "map"), [!!structure]);
  // Aktivní stránka = nejbližší stránka otevřeného rozsahu; pruh navigace, úsek cesty a sekce se počítají k ní.
  const activePage = activePageId(graph, scope.id);
  const groups = projectTree(graph, domain.id, activePage);
  const nav = pageNav(domainPageTree(graph, domain.id), activePage);
  const appSite = domain.site?.kind === "application" ? domain.site : undefined;
  const slices = activePage ? pageSlices(appSite, activePage, graph.nodes, derivedForDomain(props.derivedJourneys ?? [], domain.id)) : [];
  // Štítek sekce vybere stránku v Detailu; nový klíč sloupce ho otevře znovu, aby začal záložkou Stránka.
  const [detailKey, setDetailKey] = useState(0);
  const selectPage = () => { if (!activePage) return; if (selectedId !== activePage) setDetailKey((key) => key + 1); props.onSelect(activePage); };
  const path = scopePath(graph, scope.id, domain.id);
  const motion = useMapMotion({ graph, scopeId: scope.id, pageId: activePage, states: props.cards.states, journeys: props.cards.journeys });
  const empty = !graph.nodes.some((node) => node.parentId === scope.id);
  const toggle = <div className="page-editor__switch" role="group" aria-label="Co zobrazit">
    <button type="button" className="page-editor__switch-button" aria-pressed={focus === "map"} onClick={() => setFocus("map")}>Mapa</button>
    <button type="button" className="page-editor__switch-button" aria-pressed={focus === "structure"} onClick={() => setFocus("structure")}>Struktura</button>
  </div>;
  return <div className={pageLayoutClass({ structure: !!structure, detail: !!detail, focus })} data-testid="architecture-page-editor">
    <PageSidebar projectName={props.projectName} groups={groups} scopeName={scope.name} disabled={disabled} treeDisabled={props.structureDisabled ?? disabled}
      onOpenPage={props.onOpenPage} onAddPage={props.onAddPage} onInsert={(id) => props.onInsert(id)}/>
    <main className="page-editor__map" aria-label="Mapa architektury">
      <header className="page-editor__map-head">
        <PageIcon name="area" size={22} className="page-editor__map-icon"/>
        <div className="page-editor__map-text">
          <h2 className="page-editor__map-title">Mapa architektury — {scope.name}</h2>
          <p className="page-editor__map-lead">Přehled komponent a jejich propojení na stránce</p>
        </div>
        {props.webBadge}
        {activePage && props.decompose && <PageDecomposeCopy pageId={activePage} variant="header" {...props.decompose(activePage)}/>}
        {structure && toggle}
      </header>
      {path.length > 1 && <nav className="page-editor__crumbs" aria-label="Cesta mapou">
        {path.map((node, index) => <button key={node.id} type="button" className="page-editor__crumb" aria-current={index === path.length - 1 ? "page" : undefined}
          onClick={() => props.onOpenScope(node.id)}>{node.name}</button>)}
      </nav>}
      <PageNav nav={nav} onOpen={(id) => props.onOpenPage(domain.id, id)}/>
      {activePage && <JourneySlice key={activePage} slices={slices} sections={sectionChips(graph, activePage)} onOpenPage={(id) => props.onOpenPage(domain.id, id)}
        onOpenJourneys={props.onOpenJourneys} onSelectPage={selectPage}/>}
      <div className="page-editor__stage">
        <ArchitectureCanvas key={props.editorId + ":" + scope.id} graph={graph} scopeId={scope.id} editorId={props.editorId} selected={selectedId}
          disabled={disabled} revealId={props.reveal} onSelect={props.onSelect} onOpenPage={(id) => props.onOpenPage(domain.id, id)} onOpenStructure={props.onOpenStructure} onOpenEditor={props.onOpenEditor}
          onAddNode={props.onAddNode} onSector={props.onSector} onMove={props.onMove} onConnect={props.onConnect} onResize={props.onResize} onRemoveEdge={props.onRemoveEdge}
          onInsert={(id, target, point, link) => props.onInsert(id, target, point, link)} life={{ states: props.cards.states, motion }}/>
        {empty && <div className="page-editor__empty">
          <h3 className="page-editor__empty-title">{scope.name}</h3>
          <p className="page-editor__empty-text">Prázdná mapa této stránky. Začněte oblastí nebo přetáhněte prvek z Knihovny.</p>
          <button type="button" className="page-editor__empty-button" disabled={disabled} onClick={props.onArea}>+ Přidat oblast</button>
        </div>}
      </div>
    </main>
    {structure && <section className="page-editor__structure"><div className="page-editor__structure-bar">{toggle}</div>{structure}</section>}
    {detail && <aside key={detailKey} className="page-editor__detail" aria-label="Detail prvku">{detail}</aside>}
  </div>;
}
