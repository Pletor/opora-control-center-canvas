import { useState } from "react";
import type { DomainChoice } from "../logic/domain-choices";

/**
 * „Přiřadit k doméně“ pod nepřiřazeným worktree: výběr domény a potvrzení. Chybu backendu (např.
 * endpoint ještě neběží) ukáže větou u řádku; po úspěchu worktree sám odejde do své domény.
 */
export default function AssignDomainRow({ worktreeId, name, choices, onAssign }: {
  worktreeId: string; name: string; choices: DomainChoice[]; onAssign: (worktreeId: string, domainId: string) => Promise<void>;
}) {
  const [domainId, setDomainId] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  async function submit() {
    setSaving(true); setError("");
    try { await onAssign(worktreeId, domainId); }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setSaving(false); }
  }
  if (!choices.length) return <p className="arch-landing__assign-empty">Nejdřív založte doménu, pak sem worktree přiřadíte.</p>;
  return <form className="arch-landing__assign" data-testid={"assign-domain-" + worktreeId} onSubmit={(event) => { event.preventDefault(); void submit(); }}>
    <label className="arch-landing__assign-label">Přiřadit {name} k doméně
      <select className="arch-landing__assign-select" disabled={saving} value={domainId} data-testid={"assign-domain-select-" + worktreeId} onChange={(event) => setDomainId(event.target.value)}>
        <option value="">Vyberte doménu…</option>
        {choices.map((choice) => <option key={choice.id} value={choice.id}>{choice.label}</option>)}
      </select>
    </label>
    <button type="submit" className="arch-landing__quiet" disabled={saving || !domainId} data-testid={"assign-domain-save-" + worktreeId}>{saving ? "Přiřazuji…" : "Přiřadit"}</button>
    {error && <p className="arch-landing__assign-error" role="alert">{error}</p>}
  </form>;
}
