import type { CanvasNode } from "@/shared/types/logic/types";
import type { ProductBranch } from "@/project/product-tree/logic/product-tree";
import CopyIdButton from "@/ui-kit/copy-id/components/CopyIdButton";
import PageJourneys from "./PageJourneys";
import PageSections from "./PageSections";
import type { PageJourneyRole } from "../logic/page-journeys";
import { holesLabel, type CardState } from "../../card-state/logic/card-state";
import CardIcon from "../../card-state/components/CardIcon";
import CardStateChip from "../../card-state/components/CardStateChip";
import PageDecomposeCopy from "../../page-editor/page-decompose/components/PageDecomposeCopy";
import type { PageDecompose } from "../../page-editor/page-decompose/logic/page-decompose-prompt";

type Actions = {
  disabled: boolean; onOpen: (id: string) => void; onAdd: (parentId: string) => void; onEdit: (node: CanvasNode) => void;
  onReorder: (id: string, direction: -1 | 1) => void; onMove: (id: string) => void; onRemove: (id: string) => void;
};

/** Live work on pages: how many worktrees touch each page and which pages the selected worktree touches. */
export type PageWork = { counts: Map<string, number>; highlighted: Set<string> };

/** Karta stránky v jazyce karet Studia: hlavička s ikonou stránky, názvem (otevře Editor stránky), štítkem stavu a tichým
 * čipem ID; pod ní cesta, cíl, účel, sekce, cesty zákazníka a podstránky (rekurzivně); pata se souhrnem, dírami,
 * odznakem worktree a tichými akcemi struktury (i „Kopírovat zadání rozkladu“ pro agenta). Rám nese barvu stavu, „staví se“ dýchá. */
export default function PageCard({ branch, index, count, actions, work, journeyRoles, states, decompose }: {
  branch: ProductBranch; index: number; count: number; actions: Actions; work?: PageWork; journeyRoles?: Map<string, PageJourneyRole[]>;
  states?: ReadonlyMap<string, CardState>;
  /** Zadání rozkladu stránky pro agenta (§5.2), skládá rodič; chybí = bez tlačítka „Kopírovat zadání rozkladu“. */
  decompose?: PageDecompose;
}) {
  const { node, children } = branch;
  const { disabled } = actions;
  const workCount = work?.counts.get(node.id) ?? 0;
  const state = states?.get(node.id);
  const tone = state ? ` card-state--${state.state}${state.state === "building" ? " card-state__frame--building" : ""}` : "";
  return <article className={"domain-map__card" + (work?.highlighted.has(node.id) ? " domain-map__card--highlighted" : "") + tone} data-testid={"architecture-page-card-" + node.id} data-state={state?.state}>
    <header className="domain-map__card-head">
      <CardIcon node={node} className="domain-map__card-icon"/>
      <button type="button" className="domain-map__card-title" title={node.name} data-testid={"architecture-page-open-" + node.id} onClick={() => actions.onOpen(node.id)}>{node.name} ↗</button>
      <CardStateChip state={state} testId={"architecture-page-state-" + node.id}/>
      <CopyIdButton id={node.id} label="ID stránky"/>
    </header>
    <div className="domain-map__card-body">
      <span className="domain-map__card-kind">Stránka{node.site?.kind === "page" && <code className="domain-map__path">{node.site.path}</code>}</span>
      {node.site?.kind === "page" && node.site.goal && <p className="domain-map__goal" title={node.site.goal} data-testid={"architecture-page-goal-" + node.id}>{node.site.goal}</p>}
      {node.purpose && <p className="domain-map__card-purpose">{node.purpose}</p>}
      {node.site?.kind === "page" && <PageSections sections={node.site.sections}/>}
      <PageJourneys roles={journeyRoles?.get(node.id) ?? []} pageId={node.id}/>
      <div className="domain-map__subpages">
        {children.map((child, i) => <PageCard key={child.node.id} branch={child} index={i} count={children.length} actions={actions} work={work} journeyRoles={journeyRoles} states={states} decompose={decompose}/>)}
        {!children.length && <p className="domain-map__empty">Zatím bez podstránek</p>}
        <button type="button" className="domain-map__sub-add" disabled={disabled} data-testid={"architecture-add-page-" + node.id} onClick={() => actions.onAdd(node.id)}>+ Podstránka</button>
      </div>
    </div>
    {(state || workCount > 0) && <footer className="domain-map__card-foot">
      <span className="domain-map__card-summary" title={state?.summary}>{state?.summary ?? ""}</span>
      {state && state.holes > 0 && <span className="domain-map__card-holes" title="Díry mapy pod touto stránkou">{holesLabel(state.holes)}</span>}
      {workCount > 0 && <span className="domain-map__work" title="Worktree, které na této stránce nebo jejích podstránkách pracují">{workCount} worktree</span>}
    </footer>}
    <nav className="domain-map__card-actions" aria-label={`Úpravy stránky ${node.name}`}>
      <button type="button" disabled={disabled} onClick={() => actions.onEdit(node)}>Upravit</button>
      <button type="button" disabled={disabled || index === 0} aria-label={`Posunout ${node.name} dříve`} data-testid={"architecture-page-up-" + node.id} onClick={() => actions.onReorder(node.id, -1)}>←</button>
      <button type="button" disabled={disabled || index === count - 1} aria-label={`Posunout ${node.name} později`} data-testid={"architecture-page-down-" + node.id} onClick={() => actions.onReorder(node.id, 1)}>→</button>
      <button type="button" disabled={disabled} data-testid={"architecture-page-move-" + node.id} onClick={() => actions.onMove(node.id)}>Přesunout</button>
      {decompose && <PageDecomposeCopy pageId={node.id} {...decompose(node.id)}/>}
      <button type="button" className="domain-map__danger" disabled={disabled} data-testid={"architecture-page-delete-" + node.id} onClick={() => actions.onRemove(node.id)}>Smazat</button>
    </nav>
  </article>;
}
