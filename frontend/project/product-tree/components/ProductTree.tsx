import { useMemo } from "react";
import type { CanvasNode } from "@/shared/types/logic/types";
import { productTree, type ProductBranch } from "../logic/product-tree";
import "../styles/product-tree.css";

export type ProductTreeProps = {
  nodes: CanvasNode[]; workspace: string; readOnly: boolean; busy: boolean;
  onOpenDomain: (id: string | null) => void; onChooseWorkspace: () => void;
};

/** Source maps link to the authoritative domain map; they do not own another page editor. */
export default function ProductTree({ nodes, workspace, readOnly, busy, onOpenDomain, onChooseWorkspace }: ProductTreeProps) {
  const tree = useMemo(() => productTree(nodes), [nodes]);
  function rows(branches: ProductBranch[], domainId?: string) {
    return <ul className="product-tree__list">{branches.map(({ node, children }) => <li key={node.id} data-testid={"product-node-" + node.id}><details open className="product-tree__branch"><summary className="product-tree__row"><strong>{node.name}</strong></summary>
      {node.site?.kind === "application" ? node.site.environments.map((env) => <div className="product-tree__host" key={env.host}><span>{env.name}</span><code>{env.host}</code></div>) : node.site?.kind === "page" ? <code>{node.site.path}</code> : null}
      <button type="button" className="product-tree__open" data-testid={"product-open-" + node.id} onClick={() => onOpenDomain(domainId ?? node.id)}>Otevřít mapu domény</button>{children.length > 0 && rows(children, domainId ?? node.id)}
    </details></li>)}</ul>;
  }
  return <section className="product-tree" aria-label="Aplikace a stránky" data-testid="product-tree"><header><h3>Domény a stránky</h3><small>Pracovní prostor: <strong>{workspace}</strong></small></header>
    {readOnly && <p className="product-tree__notice">Tento pohled je pouze ke čtení. <button type="button" disabled={busy} onClick={onChooseWorkspace}>Vybrat pracovní prostor</button></p>}
    {rows(tree)}<button type="button" data-testid="product-open-architecture" onClick={() => onOpenDomain(null)}>Otevřít architekturu projektu</button>
  </section>;
}
