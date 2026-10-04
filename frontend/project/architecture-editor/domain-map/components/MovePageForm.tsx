import { useState } from "react";
import type { CanvasNode } from "@/shared/types/logic/types";

/** Pick a new parent for a page (or the main navigation) and confirm. */
export default function MovePageForm({ domainId, candidates, disabled, onSubmit, onCancel }: {
  domainId: string; candidates: CanvasNode[]; disabled: boolean; onSubmit: (parentId: string) => Promise<void>; onCancel: () => void;
}) {
  const [parentId, setParentId] = useState(domainId);
  const [error, setError] = useState("");
  return <form className="ae-form ae-product-form" onSubmit={(event) => { event.preventDefault(); void onSubmit(parentId).catch((cause) => setError(String(cause))); }}>
    <h3>Přesunout stránku</h3>
    <label>Nadřazená stránka
      <select disabled={disabled} data-testid="architecture-page-parent" value={parentId} onChange={(event) => setParentId(event.target.value)}>
        <option value={domainId}>Hlavní navigace</option>
        {candidates.map((node) => <option key={node.id} value={node.id}>{node.name}</option>)}
      </select>
    </label>
    {error && <p role="alert">{error}</p>}
    <div className="ae-row">
      <button disabled={disabled} data-testid="architecture-page-move-save">Přesunout</button>
      <button type="button" disabled={disabled} onClick={onCancel}>Zrušit</button>
    </div>
  </form>;
}
