import type { CanvasNode } from "@/shared/types/logic/types";
import type { ProductBranch } from "@/project/product-tree/logic/product-tree";
import CopyIdButton from "@/ui-kit/copy-id/components/CopyIdButton";
import PageSections from "./PageSections";

type Actions = {
  disabled: boolean; onOpen: (id: string) => void; onAdd: (parentId: string) => void; onEdit: (node: CanvasNode) => void;
  onReorder: (id: string, direction: -1 | 1) => void; onMove: (id: string) => void; onRemove: (id: string) => void;
};

/** Live work on pages: how many worktrees touch each page and which pages the selected worktree touches. */
export type PageWork = { counts: Map<string, number>; highlighted: Set<string> };

/** One page card with a quiet ID chip, a worktree badge, sub-pages inside it and a quiet footer of structural actions; recursive for sub-pages. */
export default function PageCard({ branch, index, count, actions, work }: { branch: ProductBranch; index: number; count: number; actions: Actions; work?: PageWork }) {
  const { node, children } = branch;
  const { disabled } = actions;
  const workCount = work?.counts.get(node.id) ?? 0;
  return <article className={"domain-map__card" + (work?.highlighted.has(node.id) ? " domain-map__card--highlighted" : "")} data-testid={"architecture-page-card-" + node.id}>
    <header className="domain-map__card-head">
      <div>
        <span className="domain-map__title-row">
          <button type="button" className="domain-map__card-title" data-testid={"architecture-page-open-" + node.id} onClick={() => actions.onOpen(node.id)}>{node.name} ↗</button>
          <CopyIdButton id={node.id} label="ID stránky"/>
        </span>
        {workCount > 0 && <span className="domain-map__work" title="Worktree, které na této stránce nebo jejích podstránkách pracují">{workCount} worktree</span>}
      </div>
      <button type="button" className="domain-map__sub-add" disabled={disabled} data-testid={"architecture-add-page-" + node.id} onClick={() => actions.onAdd(node.id)}>+ Podstránka</button>
    </header>
    {node.site?.kind === "page" && <code className="domain-map__path">{node.site.path}</code>}
    {node.site?.kind === "page" && node.site.goal && <p className="domain-map__goal" title={node.site.goal} data-testid={"architecture-page-goal-" + node.id}>{node.site.goal}</p>}
    {node.purpose && <p className="domain-map__card-purpose">{node.purpose}</p>}
    {node.site?.kind === "page" && <PageSections sections={node.site.sections}/>}
    <div className="domain-map__subpages">
      {children.map((child, i) => <PageCard key={child.node.id} branch={child} index={i} count={children.length} actions={actions} work={work}/>)}
      {!children.length && <p className="domain-map__empty">Zatím bez podstránek</p>}
    </div>
    <footer className="domain-map__card-foot">
      <button type="button" disabled={disabled} onClick={() => actions.onEdit(node)}>Upravit</button>
      <button type="button" disabled={disabled || index === 0} aria-label={`Posunout ${node.name} dříve`} data-testid={"architecture-page-up-" + node.id} onClick={() => actions.onReorder(node.id, -1)}>←</button>
      <button type="button" disabled={disabled || index === count - 1} aria-label={`Posunout ${node.name} později`} data-testid={"architecture-page-down-" + node.id} onClick={() => actions.onReorder(node.id, 1)}>→</button>
      <button type="button" disabled={disabled} data-testid={"architecture-page-move-" + node.id} onClick={() => actions.onMove(node.id)}>Přesunout</button>
      <button type="button" className="domain-map__danger" disabled={disabled} data-testid={"architecture-page-delete-" + node.id} onClick={() => actions.onRemove(node.id)}>Smazat</button>
    </footer>
  </article>;
}
