// Povýšit závěr výzkumu do zadání: nová revize rodičovského fragmentu s poznámkou a odkazem na výzkum
// (server ho zapíše do poznámky). Text rodiče se předvyplní a člověk do něj závěr zapracuje.
import { useState } from "react";
import { useFragmentDetail } from "@/editor/node-detail/brief-vault/logic/use-brief-vault";
import { vaultOp, type VaultScope } from "../logic/vault-actions";

export default function PromoteForm({ scope, researchId, parentId, approach, onDone }: {
  scope: VaultScope;
  researchId: string;
  parentId: string;
  approach: string;
  onDone: (message: string) => void;
}) {
  const { detail, error } = useFragmentDetail(scope.project, scope.workspace, parentId, null, null);
  const [text, setText] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  if (error) return <p className="vault-window__error" role="alert">{error}</p>;
  if (!detail) return <p className="vault-window__notice" role="status">Načítám zadání…</p>;
  const value = text ?? detail.fragment.text + (approach ? "\n\n" + approach : "");
  async function submit() {
    setBusy(true); setFailure("");
    try {
      const result = await vaultOp<{ fragment: { revision: number } }>(scope, { op: "promote", fragmentId: researchId,
        expectedRevision: detail!.latestRevision, note: note.trim(), text: value });
      onDone(`Zadání „${detail!.fragment.title}“ má novou revizi r${result.fragment.revision}.`);
    } catch (e) { setFailure(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  return (
    <div className="vault-panel" aria-label="Povýšit do zadání">
      <h4 className="vault-panel__title">Nová revize „{detail.fragment.title}“ (teď r{detail.latestRevision})</h4>
      <label className="vault-field">Text zadání po povýšení
        <textarea rows={8} value={value} onChange={(event) => setText(event.target.value)} />
      </label>
      <label className="vault-field">Proč (poznámka revize, povinná)
        <input value={note} maxLength={900} onChange={(event) => setNote(event.target.value)} placeholder="Doplněn postup z výzkumu" />
      </label>
      <div className="vault-actions">
        <button type="button" className="vault-button vault-button--primary" disabled={busy || !note.trim()} onClick={() => void submit()}>Povýšit</button>
        {failure && <span className="vault-window__error" role="alert">{failure}</span>}
      </div>
    </div>
  );
}
