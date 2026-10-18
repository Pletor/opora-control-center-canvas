import { useEffect, useState, type ReactNode } from "react";
import type { CanvasNode } from "@/shared/types/logic/types";
import { productFingerprint, type ProductBranch, type ProductDraft } from "@/project/product-tree/logic/product-tree";
import ArchitectureProductForm from "./ArchitectureProductForm";
import DomainPanel from "./DomainPanel";
import MovePageForm from "./MovePageForm";
import PageCard, { type PageWork } from "./PageCard";
import "../styles/domain-map.css";

function flatten(branches: ProductBranch[]): CanvasNode[] {
  return branches.flatMap((branch) => [branch.node, ...flatten(branch.children)]);
}

/**
 * Step 2: the only place where structure changes: pages, sub-pages, order, navigation. The parent saves; this part reports edits upward.
 * `live` = third column (only projects with worktrees); `webBadge` = web state in the domain panel when there is no live column.
 */
export default function ArchitectureDomainMap({ domain, pages, disabled, live, webBadge, work, initialDraftParentId, onDraftOpened, onOpen, onSave, onReorder, onReparent, onRemove }: {
  domain: CanvasNode; pages: ProductBranch[]; disabled: boolean; live?: ReactNode; webBadge?: ReactNode; work?: PageWork; initialDraftParentId?: string | null; onDraftOpened?: () => void; onOpen: (id: string) => void;
  onSave: (draft: ProductDraft) => Promise<void>; onReorder: (id: string, direction: -1 | 1) => void;
  onReparent: (id: string, parentId: string) => Promise<void>; onRemove: (id: string) => void;
}) {
  const [draft, setDraft] = useState<ProductDraft | null>(null);
  const [moving, setMoving] = useState<string | null>(null);
  const add = (parentId: string) => setDraft({ parentId, name: "", purpose: "", site: { kind: "page", path: "" } });
  const edit = (node: CanvasNode) => node.site && setDraft({ id: node.id, original: productFingerprint(node), parentId: node.parentId, name: node.name, purpose: node.purpose, site: structuredClone(node.site) });
  // One-shot request from the parent: open the new-page form once, then tell the parent it was consumed.
  useEffect(() => { if (initialDraftParentId) { add(initialDraftParentId); onDraftOpened?.(); } }, [initialDraftParentId]);
  const actions = { disabled, onOpen, onAdd: add, onEdit: edit, onReorder, onMove: setMoving, onRemove };
  const host = domain.site?.kind === "application" ? domain.site.environments[0]?.host : "";
  return <div className={"ae-layout ae-layout--map" + (live ? " domain-map__frame--live" : "")} data-testid="architecture-domain-map">
    <DomainPanel domain={domain} pages={pages} disabled={disabled} badge={webBadge} onOpen={onOpen} onAdd={() => add(domain.id)}/>
    <main className="domain-map">
      <p className="domain-map__kicker">MAPA STRÁNEK · {host || domain.name}</p>
      <h2 className="domain-map__title">Navigace domény</h2>
      <p className="domain-map__lead">Hlavní stránky se zobrazují v navigaci. Podstránky patří ke svému rodiči.</p>
      {draft && <ArchitectureProductForm key={draft.id ?? draft.parentId} initial={draft} disabled={disabled} onSave={onSave} onClose={() => setDraft(null)}/>}
      {moving && <MovePageForm key={moving} domainId={domain.id} candidates={flatten(pages).filter((node) => node.id !== moving)} disabled={disabled}
        onSubmit={(parentId) => onReparent(moving, parentId).then(() => setMoving(null))} onCancel={() => setMoving(null)}/>}
      <nav className="domain-map__navbar" aria-label="Hlavní navigace stránek" data-testid="architecture-navbar">
        <strong className="domain-map__navbar-label">NAVBAR</strong>
        {pages.map(({ node }) => <button type="button" key={node.id} className="domain-map__navbar-item" onClick={() => onOpen(node.id)}>{node.name}</button>)}
      </nav>
      <div className="domain-map__grid">
        {pages.map((branch, index) => <PageCard key={branch.node.id} branch={branch} index={index} count={pages.length} actions={actions} work={work}/>)}
      </div>
      {!pages.length && <p className="domain-map__empty">Přidejte první stránku této domény.</p>}
    </main>
    {live && <div className="domain-map__live">{live}</div>}
  </div>;
}
