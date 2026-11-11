import { useEffect, useMemo, useState, type ComponentProps, type ReactNode } from "react";
import type { CanvasNode, ElementKind, Graph } from "@/shared/types/logic/types";
import { activePageId, structureRows } from "../project-tree/logic/project-tree-model";
import { nextAdmissible } from "../logic/plan-progress";
import { useCarry, type CarryItem } from "../logic/use-carry";
import { canNest, cellAt, layoutSections, type LayoutSection, type Point } from "../layout-canvas/logic/layout-grid";
import { addBox, removeBox } from "../layout-canvas/logic/layout-edit";
import { settleLayout } from "../layout-canvas/logic/settle-layout";
import { templateSections } from "../layout-canvas/logic/layout-templates";
import { pageLogic } from "../layout-canvas/logic/page-logic";
import { gridAt, sectionAt } from "../layout-canvas/logic/drop-target";
import { czechCount } from "../layout-canvas/logic/czech-count";
import PageSidebar from "./PageSidebar";
import LayoutCanvas from "../layout-canvas/components/LayoutCanvas";
import BoxPalette from "../box-palette/components/BoxPalette";
import ElementPalette from "../element-palette/components/ElementPalette";
import PlanHeader from "../plan-header/components/PlanHeader";
import PlanBar from "../plan-bar/components/PlanBar";
import { domainPageTree } from "../../logic/domain-model";
import { environmentAddress } from "../../landing/logic/domain-kind";
import { pageCheckGroups, type MapCheckGroup, type MapCheckTarget } from "../../domain-site/map-check/logic/map-check";
import type { CardLife } from "../../card-state/logic/card-state";
import PageDecomposeCopy from "../page-decompose/components/PageDecomposeCopy";
import PlanBuildButton from "../plan-build/components/PlanBuildButton";
import { buildPlan } from "../plan-build/logic/plan-build";
import type { PageDecompose } from "../page-decompose/logic/page-decompose-prompt";
import ProjectTree from "../project-tree/components/ProjectTree";
import { useSketchedBoxes } from "../logic/page-plan";
import { usePageScan } from "../plan-scan/logic/use-page-scan";
import { captureUrl, type ScanProposal } from "../plan-scan/logic/page-scan";
import type { AdoptParts, AdoptResult } from "../plan-scan/logic/adopt-scan";
import ScanDialog from "../plan-scan/components/ScanDialog";
import ScanPanel from "../plan-scan/components/ScanPanel";
import BoxDetail from "../../box-detail/components/BoxDetail";
import { patchLock, patchSection } from "../../box-detail/logic/box-detail";
import BoxFocus from "../box-focus/components/BoxFocus";
import { useBoxFocus } from "../box-focus/logic/use-box-focus";
import DesignStrip, { LookSwitch } from "../design-look/components/DesignStrip";
import { useLook } from "../design-look/logic/use-look";
import { useDesignTokens } from "../design-look/logic/use-design-tokens";
import { useInspirationFiles } from "../../box-detail/logic/use-inspiration-files";
import "../styles/page-editor.css";

type TreeProps = ComponentProps<typeof ProjectTree>;
type Layer = "layout" | "logic";
type Props = {
  project: string; workspace: string;
  graph: Graph; domain: CanvasNode;
  /** Otevřený rozsah (stránka nebo karta pod ní); `null` = doména zatím nemá stránku. */
  scope: CanvasNode | null; selectedId: string | null;
  /** `disabled` = obsah stránky (prvky logiky) včetně kompletní stránky; `structureDisabled` = struktura (Struktura a layout), zapisovatelná i na mainu. */
  disabled: boolean; structureDisabled: boolean;
  /** Věty zámků pro Detail boxu a sken (proč je skica, inspirace nebo logika jen ke čtení); `null` = odemčeno.
   * `drawing` = zámek obsahu pro kresbu zanořeného pohledu; `undefined` = přechodný stav (ukládání), platí poslední známý,
   * aby kresba při každém uložení nezmizela ani nebliknula. */
  lockText: { structure: string | null; content: string | null; drawing: string | null | undefined };
  /** Detail prvku skládá rodič a vkládá ho do pravého sloupce. */
  detail: ReactNode | null;
  /** Web state badge of the domain host in the header (docs/domeny-a-worktree.md §10.3). */
  webBadge?: ReactNode;
  /** Skutečný stav karet (Studio); počítá rodič (`useCardLife`). */
  cards: CardLife;
  /** Zadání rozkladu aktivní stránky pro agenta (docs/architektura-pro-agenty.md §5.2); skládá rodič. */
  decompose?: PageDecompose;
  /** Díry kontroly mapy domény (hotové skupiny); plátno ukáže jen díry otevřené stránky. */
  check: MapCheckGroup[] | null; onOpenFinding: (target: MapCheckTarget) => void;
  /** Stav stránky od rodiče: kompletní a zavřená pro úpravy (`sealed`) do „Otevřít k úpravám“. */
  complete: boolean; sealed: boolean; onReopen: () => void;
  tree: Pick<TreeProps, "intent" | "onSave" | "onReorder" | "onRemove">;
  onOpenPage: (pageId: string) => void; onSelect: (id: string | null) => void; onOpenEditor: (id: string) => void;
  /** Nový layout stránky (vrstva 1); ukládá rodič jednou změnou grafu. `content` = mění se inspirace boxu (zámek obsahu). */
  onLayout: (pageId: string, sections: LayoutSection[], lock?: "structure" | "content") => void;
  /** Převzít zaškrtnuté části návrhu skenu (Layout, Design, Logika a tok dat); vrátí výsledek každé části. */
  onAdoptScan: (pageId: string, proposal: ScanProposal, scanId: string, parts: AdoptParts) => Promise<AdoptResult[]>;
  /** Odkaz z pruhu Design webu do Správy webu; bez něj pruh odkaz nemá. */
  onOpenSite?: () => void;
  /** Prvek logiky do boxu (`section`) nebo na celou stránku (`null`); přesun mezi boxy a odebrání. */
  onInsertElement: (pageId: string, kind: ElementKind, label: string, section: string | null) => void;
  onMoveElement: (id: string, section: string | null) => void; onRemoveElement: (id: string) => void;
};

/** Plátno 2: Struktura a paleta | stránka jako layout (1) a logika (2) s hlavičkou a dalším přípustným krokem | detail prvku. */
export default function PageEditor(props: Props) {
  const { graph, domain, scope, selectedId, disabled, structureDisabled, detail } = props;
  const [layer, setLayer] = useState<Layer>("layout");
  const [boxId, setBoxId] = useState<string | null>(null);
  const [scanOpen, setScanOpen] = useState(false);
  const [adopting, setAdopting] = useState(false);
  const [report, setReport] = useState<{ scanId: string; results: AdoptResult[] } | null>(null);
  const [look, setLook] = useLook();
  const design = useDesignTokens(props.project);
  // Aktivní stránka = nejbližší stránka otevřeného rozsahu; strom, layout, logika a další krok se počítají k ní.
  const pageId = scope ? activePageId(graph, scope.id) : null;
  const page = graph.nodes.find((node) => node.id === pageId) ?? null;
  const pageSections = page?.site?.kind === "page" ? page.site.sections : undefined;
  // Uložená data s překryvy se kreslí usazená (bez zápisu); usazená se uloží při další úpravě struktury.
  const stored = useMemo(() => layoutSections(pageSections ?? []), [pageSections]);
  const sections = useMemo(() => settleLayout(stored), [stored]);
  const logic = page ? pageLogic(graph, page.id, new Set(sections.map((section) => section.id))) : null;
  /** Každý zápis struktury projde `settleLayout`; zápis obsahu (inspirace) vychází z uložených boxů, aby pod zámkem obsahu neměnil strukturu. */
  const layout = (next: LayoutSection[], lock?: "structure" | "content") => {
    const settled = lock === "content" ? next : settleLayout(next);
    if (page && settled !== sections && settled !== stored) props.onLayout(page.id, settled, lock);
  };
  const sketched = useSketchedBoxes(props.project, props.workspace, pageId, JSON.stringify(pageSections ?? null));
  const pageScan = usePageScan(props.project, props.workspace, pageId);
  // Pohled Design: první obrázek inspirace každého boxu přes celý box (náhledy z `/api/drawing-files`).
  const firstFiles = look === "design" ? sections.flatMap((section) => section.inspiration?.files?.slice(0, 1) ?? []) : [];
  const { previews } = useInspirationFiles(props.project, props.workspace, firstFiles);
  const covers = new Map(sections.flatMap((section) => { const src = previews.get(section.inspiration?.files?.[0] ?? ""); return src ? [[section.id, src] as const] : []; }));
  useEffect(() => setBoxId(null), [pageId]);
  // Zanořený pohled boxu (dvojklik na box, `boxId` v adrese): místo layoutu přes celou plochu plátna.
  const focus = useBoxFocus(pageId, sections);
  // Detail boxu jen nad vybranou stránkou; vybraný prvek logiky má přednost (Detail prvku). V zanoření je výchozí otevřený box.
  const box = (!selectedId || selectedId === pageId) ? sections.find((section) => section.id === (boxId ?? focus.id)) ?? null : null;
  const selectBox = (id: string) => { setBoxId(id); if (page && selectedId !== page.id) props.onSelect(page.id); };
  const openBox = (id: string) => { selectBox(id); focus.open(id); };
  const selectNode = (id: string | null) => { setBoxId(null); props.onSelect(id); };
  /** Převzetí po částech: panel pak ukáže, co se převzalo a co ne; tokeny pruhu Design webu se načtou znovu. */
  function adopt(parts: AdoptParts) {
    if (!page || pageScan.scan.phase !== "done") return;
    const { scanId, proposal } = pageScan.scan;
    setAdopting(true);
    props.onAdoptScan(page.id, proposal, scanId, parts)
      .then((results) => { setReport({ scanId, results }); design.reload(); },
        (cause) => setReport({ scanId, results: [{ part: "layout", ok: false, text: cause instanceof Error ? cause.message : String(cause) }] }))
      .finally(() => setAdopting(false));
  }
  const scanReport = report && pageScan.scan.phase === "done" && report.scanId === pageScan.scan.scanId ? report.results : null;
  function drop(item: CarryItem, point: Point) {
    if (!page) return;
    if (item.kind === "box") {
      const target = structureDisabled ? null : gridAt(point);
      if (target && canNest(sections, null, target.parent)) layout(addBox(sections, item.box, target.parent, cellAt(target.rect, point)));
      return;
    }
    const section = disabled ? undefined : sectionAt(point);
    if (section === undefined) return;
    if (item.kind === "logic") props.onInsertElement(page.id, item.element, item.label, section);
    else if ((item.node.card?.section ?? null) !== section) props.onMoveElement(item.node.id, section);
  }
  const carry = useCarry(drop);
  function template(id: string) {
    if (sections.length && !window.confirm(`Šablona nahradí celý layout stránky (${czechCount(sections.length, ["box", "boxy", "boxů"])}). Prvky logiky z odebraných boxů přejdou na celou stránku. Pokračovat?`)) return;
    layout(templateSections(id, sections));
  }
  const host = domain.site?.kind === "application" ? environmentAddress(domain.site.environments[0]) : "";
  const palette = !page ? null : layer === "layout"
    ? <BoxPalette disabled={structureDisabled} onAdd={(box) => layout(addBox(sections, box, null))} onCarry={(box, event) => carry.start({ kind: "box", box }, event)} onTemplate={template}/>
    : <ElementPalette disabled={disabled} onInsert={(kind, label) => props.onInsertElement(page.id, kind, label, null)} onCarry={(element, label, event) => carry.start({ kind: "logic", element, label }, event)}/>;
  const ghost = carry.carrying?.item;
  const aside = page && box ? <BoxDetail key={box.id}
    project={props.project} workspace={props.workspace} pageId={page.id} section={box} nodes={logic?.byBox.get(box.id) ?? []} states={props.cards.states}
    layoutLock={props.lockText.structure} contentLock={props.lockText.content}
    onChange={(patch) => layout(patchSection(patchLock(patch) === "content" ? stored : sections, box.id, patch), patchLock(patch))}
    onDiscard={() => { setBoxId(null); layout(removeBox(sections, box.id)); }}
    onSelectElement={selectNode} onClose={() => setBoxId(null)} onSketchSaved={sketched.refresh} sketch={box.id !== focus.id}/> : detail;
  return <div className={"page-editor" + (aside ? " page-editor--detail" : "")} data-testid="architecture-page-editor">
    <PageSidebar tree={{ ...props.tree, domain, title: host || domain.name, rows: structureRows(domainPageTree(graph, domain.id), pageId), disabled: structureDisabled, onOpenPage: props.onOpenPage }}
      palette={palette}/>
    <main className="page-editor__map" aria-label="Plán stránky">
      {page && focus.id ? <BoxFocus project={props.project} workspace={props.workspace} pageId={page.id} pageName={page.name} sections={sections} focusId={focus.id}
        selectedBox={box?.id ?? null} lock={props.lockText.drawing} onOpen={openBox} onSelectBox={selectBox} onLeave={(parent) => (parent ? openBox(parent) : focus.close())}
        onSketchSaved={sketched.refresh}/>
      : page && logic ? <>
        <PlanHeader title={page.name} complete={props.complete} sealed={props.sealed} onReopen={props.onReopen}
          check={props.check ? pageCheckGroups(props.check, page.id) : null} onOpenFinding={props.onOpenFinding}
          tools={<>{props.webBadge}{props.decompose && <PageDecomposeCopy pageId={page.id} variant="header" {...props.decompose(page.id)}/>}
            <PlanBuildButton pageId={page.id} domainId={domain.id} onOpenEditor={props.onOpenEditor}
              onBuild={(id) => buildPlan({ project: props.project, workspace: props.workspace }, id)}/></>}
          onScan={() => setScanOpen(true)} scanBusy={pageScan.scan.phase !== "idle"}/>
        {scanOpen && <ScanDialog onStart={(url, note) => void pageScan.start(url, note)} onClose={() => setScanOpen(false)}/>}
        <div className="page-editor__toolbar">
          <div className="page-editor__layers" role="group" aria-label="Vrstva plátna">
            {(["layout", "logic"] as const).map((value, index) => <button key={value} type="button" className="page-editor__layer" aria-pressed={layer === value}
              data-testid={"architecture-layer-" + value} onClick={() => setLayer(value)}>{index + 1} {value === "layout" ? "Layout" : "Logika"}</button>)}
          </div>
          {layer === "layout" && <LookSwitch look={look} onChange={setLook}/>}
          {logic.legacy > 0 && <p className="page-editor__legacy" data-testid="architecture-legacy-cards">{czechCount(logic.legacy, ["starší karta", "starší karty", "starších karet"])} jen v Editoru
            <button type="button" className="page-editor__legacy-open" onClick={() => props.onOpenEditor(page.id)}>Otevřít v Editoru →</button></p>}
        </div>
        <div className={"page-editor__stage" + (pageScan.scan.phase !== "idle" ? " page-editor__stage--scan" : "")}>
          <div className="page-editor__canvas">
          {layer === "layout" && look === "design" && <DesignStrip tokens={design.tokens} onOpenSite={props.onOpenSite}/>}
          <LayoutCanvas layer={layer} look={look} covers={covers} sections={sections} logic={logic} states={props.cards.states} selectedId={selectedId}
            layoutDisabled={structureDisabled} logicDisabled={disabled} onLayout={layout} onSelect={selectNode} onRemoveElement={props.onRemoveElement}
            onCarry={(node, event) => carry.start({ kind: "chip", node }, event)} selectedBox={box?.id ?? null} onSelectBox={selectBox} onOpenBox={openBox} sketches={sketched.ids}/>
          </div>
          <ScanPanel scan={pageScan.scan} report={scanReport} tokens={design.tokens} layoutLock={props.lockText.structure} contentLock={props.lockText.content}
            captureSrc={(name) => captureUrl({ project: props.project, workspace: props.workspace }, pageScan.scan.phase === "done" ? pageScan.scan.scanId : "", name)}
            adopting={adopting} discardError={pageScan.discardError} onAdopt={adopt} onCancel={pageScan.reset} onDiscard={() => void pageScan.discard()}/>
        </div>
        <PlanBar next={nextAdmissible(graph, page.id, props.cards.states)} onOpenEditor={props.onOpenEditor}/>
      </> : <div className="page-editor__empty" data-testid="architecture-domain-empty">
        <h3 className="page-editor__empty-title">{host || domain.name}</h3>
        <p className="page-editor__empty-text">Doména zatím nemá stránku. Založte první stránku ve Struktuře tlačítkem + Stránka.</p>
      </div>}
    </main>
    {aside && <aside className="page-editor__detail" aria-label={box ? "Detail boxu" : "Detail prvku"}>{aside}</aside>}
    {ghost && <div className="page-editor__ghost" style={{ left: carry.carrying!.at.x + 12, top: carry.carrying!.at.y + 12 }} aria-hidden="true">
      {ghost.kind === "box" ? ghost.box.name : ghost.kind === "logic" ? ghost.label : ghost.node.name}</div>}
  </div>;
}
