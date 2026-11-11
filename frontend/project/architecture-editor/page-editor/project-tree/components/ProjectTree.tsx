import { useState } from "react";
import "../styles/project-tree.css";
import type { CanvasNode } from "@/shared/types/logic/types";
import { productFingerprint, type ProductDraft } from "@/project/product-tree/logic/product-tree";
import type { IntentEntry } from "@/project/intent-canvas/intent-entry/components/IntentButton";
import ArchitectureProductForm from "../../../domain-site/components/ArchitectureProductForm";
import type { TreePage } from "../logic/project-tree-model";
import PageIcon from "../../components/PageIcon";
import PageDialog from "../../page-dialog/components/PageDialog";

type Props = {
  domain: CanvasNode; title: string; rows: TreePage[]; disabled: boolean; intent?: IntentEntry;
  onOpenPage: (pageId: string) => void; onSave: (draft: ProductDraft) => Promise<void>;
  onReorder: (pageId: string, direction: -1 | 1) => void; onRemove: (pageId: string) => void;
};

/** Struktura otevřené domény: strom stránek a podstránek. Tady se stránky zakládají (vyskakovací okno `PageDialog`),
 * upravují (formulář stránky), posouvají a odstraňují; rozepsané okno a formulář drží dílek, uložení a mazání hlásí rodiči. */
export default function ProjectTree({ domain, title, rows, disabled, intent, onOpenPage, onSave, onReorder, onRemove }: Props) {
  const [draft, setDraft] = useState<ProductDraft | null>(null);
  const [adding, setAdding] = useState<CanvasNode | null>(null);
  const add = (parent: CanvasNode) => { setDraft(null); setAdding(parent); };
  const edit = (node: CanvasNode) => node.site && setDraft({ id: node.id, original: productFingerprint(node), parentId: node.parentId, name: node.name, purpose: node.purpose, site: structuredClone(node.site) });
  return <nav className="project-tree" aria-label="Struktura">
    <div className="project-tree__head">
      <h3 className="project-tree__title"><PageIcon name="tree" size={15}/>{title}</h3>
      <button type="button" className="project-tree__add" disabled={disabled} data-testid={"architecture-add-page-" + domain.id} onClick={() => add(domain)}>+ Stránka</button>
    </div>
    <ul className="project-tree__pages">
      {rows.map(({ node, path, depth, active, first, last }) => <li key={node.id} className={"project-tree__row" + (active ? " project-tree__row--active" : "")}
        style={{ paddingLeft: depth * 14 }} data-testid={"architecture-tree-" + node.id}>
        <button type="button" className="project-tree__page" aria-current={active ? "page" : undefined} data-testid={"architecture-open-" + node.id}
          title={path ?? undefined} onClick={() => onOpenPage(node.id)}><PageIcon name="page" size={15} className="project-tree__page-icon"/>{node.name}</button>
        <span className="project-tree__tools" aria-label={`Úpravy stránky ${node.name}`}>
          <button type="button" disabled={disabled} aria-label={`Přidat podstránku do ${node.name}`} data-testid={"architecture-add-page-" + node.id} onClick={() => add(node)}>+ Podstránka</button>
          <button type="button" disabled={disabled} title="Přejmenovat" aria-label={`Upravit ${node.name}`} data-testid={"architecture-page-edit-" + node.id} onClick={() => edit(node)}>✎</button>
          <button type="button" disabled={disabled || first} aria-label={`Posunout ${node.name} výš`} data-testid={"architecture-page-up-" + node.id} onClick={() => onReorder(node.id, -1)}>↑</button>
          <button type="button" disabled={disabled || last} aria-label={`Posunout ${node.name} níž`} data-testid={"architecture-page-down-" + node.id} onClick={() => onReorder(node.id, 1)}>↓</button>
          <button type="button" className="project-tree__danger" disabled={disabled} aria-label={`Odstranit ${node.name}`} data-testid={"architecture-page-delete-" + node.id} onClick={() => onRemove(node.id)}>✕</button>
        </span>
      </li>)}
      {!rows.length && <li className="project-tree__empty">Zatím žádná stránka.</li>}
    </ul>
    {adding && <PageDialog key={adding.id} parentId={adding.id} parentName={adding.name} parentPath={adding.site?.kind === "page" ? adding.site.path : ""}
      disabled={disabled} onSave={onSave} onClose={() => setAdding(null)}/>}
    {draft && <ArchitectureProductForm key={draft.id ?? draft.parentId} initial={draft} disabled={disabled} intent={intent} onSave={onSave} onClose={() => setDraft(null)}/>}
  </nav>;
}
