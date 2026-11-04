import { useState } from "react";
import type { FlowCase, FlowNode } from "../../logic/flow-types";
import { caseFromDraft, draftOf, type CaseDraft } from "../logic/flow-cases";

type Props = { flowCase: FlowCase; nodes: readonly FlowNode[]; onSave: (flowCase: FlowCase) => void };
const AREAS = [["input", "Vstup (JSON)"], ["env", "Prostředí: tables a services (JSON)"], ["expect", "Očekávání: result, path, rows, notify (JSON)"]] as const;

/** Formulář jednoho případu. Texty drží lokálně; „Použít“ je zkontroluje a teprve platný případ pošle rodiči, neplatný
 * JSON ukáže jako větu pod polem a nic neuloží. */
export default function CaseEditor({ flowCase, nodes, onSave }: Props) {
  const [draft, setDraft] = useState<CaseDraft>(() => draftOf(flowCase));
  const [error, setError] = useState("");
  const set = (patch: Partial<CaseDraft>) => { setDraft({ ...draft, ...patch }); setError(""); };
  const submit = () => { const made = caseFromDraft(flowCase.id, draft); if ("error" in made) setError(made.error); else onSave(made.case); };
  return <form className="case-editor" data-testid="case-editor" onSubmit={(event) => { event.preventDefault(); submit(); }}>
    <label className="case-editor__field">Jméno
      <input className="case-editor__input" value={draft.name} data-testid="case-name" onChange={(event) => set({ name: event.target.value })}/></label>
    <label className="case-editor__field">Start
      <select className="case-editor__input" value={draft.start} data-testid="case-start" onChange={(event) => set({ start: event.target.value })}>
        {!nodes.some((node) => node.id === draft.start) && <option value={draft.start}>{draft.start || "— vyberte uzel —"}</option>}
        {nodes.map((node) => <option key={node.id} value={node.id}>{node.id} · {node.type}</option>)}</select></label>
    <label className="case-editor__field">Popis
      <input className="case-editor__input" value={draft.description} data-testid="case-description" onChange={(event) => set({ description: event.target.value })}/></label>
    {AREAS.map(([key, title]) => <label key={key} className="case-editor__field">{title}
      <textarea className="case-editor__input case-editor__input--code" rows={8} spellCheck={false} value={draft[key]} data-testid={`case-${key}`}
        onChange={(event) => set({ [key]: event.target.value })}/></label>)}
    <div className="case-editor__actions">
      <button type="submit" className="case-editor__save" data-testid="case-save">Použít</button>
      {error && <span className="case-editor__error" role="alert" data-testid="case-error">{error}</span>}
    </div>
  </form>;
}
