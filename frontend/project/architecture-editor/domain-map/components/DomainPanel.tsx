import type { ReactNode } from "react";
import type { CanvasNode } from "@/shared/types/logic/types";
import type { ProductBranch } from "@/project/product-tree/logic/product-tree";
import CopyIdButton from "@/ui-kit/copy-id/components/CopyIdButton";

function rows(branches: ProductBranch[], onOpen: (id: string) => void, depth: number) {
  return branches.map(({ node, children }) => <li key={node.id} data-testid={"architecture-tree-" + node.id}>
    <button type="button" className={"domain-map__page-link" + (depth ? " domain-map__page-link--sub" : "")} title={`ID stránky: ${node.id}`} data-testid={"architecture-open-" + node.id} onClick={() => onOpen(node.id)}>
      <span>{depth ? "↳ " : ""}{node.name}</span>
      {node.site?.kind === "page" && node.site.path && <small className="domain-map__page-path">{node.site.path}</small>}
    </button>
    {children.length > 0 && <ul className="domain-map__page-list">{rows(children, onOpen, depth + 1)}</ul>}
  </li>);
}

/** Left panel: which domain this is (environment · doména, host with a quiet ID chip, optional web badge, purpose), the main add button and the list of pages. */
export default function DomainPanel({ domain, pages, disabled, badge, onOpen, onAdd }: {
  domain: CanvasNode; pages: ProductBranch[]; disabled: boolean; badge?: ReactNode; onOpen: (id: string) => void; onAdd: () => void;
}) {
  const environment = domain.site?.kind === "application" ? domain.site.environments[0] : undefined;
  return <aside className="ae-sidebar domain-map__panel">
    <p className="domain-map__env">{(environment?.name ?? "Sdílená struktura").toUpperCase()} · DOMÉNA</p>
    <div className="domain-map__host-row"><h3 className="domain-map__host">{environment?.host || domain.name}</h3><CopyIdButton id={domain.id} label="ID domény"/></div>
    {badge}
    <p className="domain-map__purpose">{domain.purpose}</p>
    <button type="button" className="domain-map__add" disabled={disabled} data-testid={"architecture-add-page-" + domain.id} onClick={onAdd}>+ Přidat stránku</button>
    <h4 className="domain-map__list-title">Seznam stránek</h4>
    <ul className="domain-map__page-list">{rows(pages, onOpen, 0)}</ul>
    {!pages.length && <p className="domain-map__empty">Stránky přidáte tlačítkem výše.</p>}
  </aside>;
}
