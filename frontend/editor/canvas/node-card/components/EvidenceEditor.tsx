import { useEffect, useRef, useState } from "react";
import type { CompletionEvidence, Proof } from "./CardEvidence";
import { useScopedSaveParticipant } from "@/shared/hooks/logic/save-scope-context";

const empty = (): CompletionEvidence => ({ tests: { status: "pending", url: "", note: "" }, review: { status: "pending", url: "", note: "" }, merge: { status: "pending", url: "", note: "" }, checksRun: [] });
export default function EvidenceEditor({ nodeId, evidence, disabled, save }: {
  nodeId: string; evidence?: CompletionEvidence; disabled: boolean; save: (value: CompletionEvidence) => Promise<boolean>;
}) {
  const stored = JSON.stringify(evidence ?? empty());
  const [draft, setDraft] = useState<CompletionEvidence>(() => JSON.parse(stored));
  const previous = useRef(stored);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { const old = previous.current; previous.current = stored;
    setDraft(current => JSON.stringify(current) === old ? JSON.parse(stored) : current);
  }, [stored]);
  const dirty = JSON.stringify(draft) !== stored;
  useScopedSaveParticipant({ id: `evidence:${nodeId}`, label: "Důkazy dokončení", dirty, isDirty: () => dirty,
    blocked: "Uložte nebo zrušte rozepsané důkazy dokončení." });
  async function commit() {
    setBusy(true); setError("");
    try { if (!await save(draft)) setError("Důkazy se nepodařilo uložit. Zkontrolujte odkazy a stav karty."); }
    catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }
  return <details><summary>Upravit důkazy</summary><fieldset disabled={disabled || busy}>
    {(["tests", "review", "merge"] as const).map(kind => <fieldset key={kind}>
      <legend>{kind}</legend>
      <select aria-label={`Stav ${kind}`} value={draft[kind].status} onChange={e => setDraft({ ...draft, [kind]: { ...draft[kind], status: e.target.value as Proof["status"] } })}>
        <option value="pending">Nedoloženo</option><option value="passed">Úspěšné</option><option value="failed">Neúspěšné</option><option value="not_applicable">Nevztahuje se</option>
      </select>
      <input aria-label={`Odkaz ${kind}`} type="url" maxLength={2048} placeholder="https://…" value={draft[kind].url} onChange={e => setDraft({ ...draft, [kind]: { ...draft[kind], url: e.target.value } })} />
      <textarea aria-label={`Zdůvodnění ${kind}`} maxLength={4000} value={draft[kind].note} onChange={e => setDraft({ ...draft, [kind]: { ...draft[kind], note: e.target.value } })} />
    </fieldset>)}
    {draft.checksRun.map((run, index) => <fieldset key={index}><legend>Kontrola {index + 1}</legend>
      {(["checkId", "command", "logUrl", "at"] as const).map(key => <label key={key}>{key}<input value={run[key]}
        onChange={e => setDraft({ ...draft, checksRun: draft.checksRun.map((r, i) => i === index ? { ...r, [key]: e.target.value } : r) })} /></label>)}
      <label>Návratový kód<input type="number" value={run.exitCode} onChange={e => setDraft({ ...draft, checksRun: draft.checksRun.map((r, i) => i === index ? { ...r, exitCode: Number(e.target.value) } : r) })} /></label>
      <button type="button" onClick={() => setDraft({ ...draft, checksRun: draft.checksRun.filter((_, i) => i !== index) })}>Odebrat kontrolu</button>
    </fieldset>)}
    <button type="button" disabled={draft.checksRun.length >= 200} onClick={() => setDraft({ ...draft, checksRun: [...draft.checksRun, { checkId: "", command: "", logUrl: "", at: "", exitCode: 0 }] })}>Přidat provedenou kontrolu</button>
    <button type="button" disabled={!dirty} onClick={() => void commit()}>Uložit důkazy</button>
    <button type="button" disabled={!dirty} onClick={() => setDraft(JSON.parse(stored))}>Zrušit změny</button>
    {error && <p role="alert">{error}</p>}
  </fieldset></details>;
}
