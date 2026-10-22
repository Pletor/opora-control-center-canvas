import { useState } from "react";
import { api } from "@/shared/types/logic/types";
import { changesetPayload, type PlanContext, type PlanDocument } from "@/hub/plan-changes/logic/plan-changes";

type Props = {
  project: string; workspace: string; context: PlanContext | null; working: PlanDocument | null; accepted: PlanDocument | null;
  changes: number; readOnly: boolean; onChanged: () => void;
};

/** Pata Zadání: pracovní změny odešle jako návrh (changeset) k přijetí člověkem, nebo je zahodí. */
export default function SpecProposal({ project, workspace, context, working, accepted, changes, readOnly, onChanged }: Props) {
  const [subject, setSubject] = useState("");
  const [state, setState] = useState({ busy: false, text: "", tone: "gap" as "ok" | "bad" | "gap" });
  const blocked = readOnly || !!context?.readOnly ? "Prostor je jen ke čtení." : !context?.acceptedHead ? "Nejprve přijměte základ zadání v OporaHubu."
    : !accepted ? "Karta ještě není v přijatém základu." : !changes ? "Pracovní zadání se neliší od přijatého." : "";
  async function propose() {
    if (!context || !working || blocked || !subject.trim()) return;
    setState({ busy: true, text: "Odesílám návrh…", tone: "gap" });
    try {
      await api("/api/oporahub/changesets", changesetPayload(project, workspace, subject, context, working, { ...working.fields }));
      setSubject(""); setState({ busy: false, text: "✓ Návrh uložen; přijímá ho člověk. Běžící běh dál pracuje se svým snímkem.", tone: "ok" });
      onChanged();
    } catch (error) { setState({ busy: false, text: `✕ ${error instanceof Error ? error.message : String(error)}`, tone: "bad" }); }
  }
  async function discard() {
    if (!working || !accepted || readOnly || !window.confirm("Zahodit pracovní změny zadání a vrátit přijatou verzi?")) return;
    setState({ busy: true, text: "Vracím přijatou verzi…", tone: "gap" });
    try {
      await api("/api/node-spec", { project, workspace, node: working.nodeId, expected_revision: working.revision, fields: { ...accepted.fields } });
      setState({ busy: false, text: "✓ Pracovní zadání vráceno na přijatou verzi.", tone: "ok" });
      onChanged();
    } catch (error) { setState({ busy: false, text: `✕ ${error instanceof Error ? error.message : String(error)}`, tone: "bad" }); }
  }
  return <section className="spec-tab__propose" aria-label="Navrhnout změnu zadání" data-oh-propose={blocked ? "blocked" : "ready"} data-oh-working-changes={changes}>
    <div className="spec-tab__propose-text">
      <b>Pracovní změny: {changes}</b>
      <span className="spec-tab__muted">{blocked || "uloženo · neodesláno"}</span>
    </div>
    <input className="spec-tab__subject" aria-label="Předmět návrhu" placeholder="Předmět návrhu (povinný)" value={subject} maxLength={200}
      disabled={!!blocked || state.busy} onChange={event => setSubject(event.target.value)} />
    <div className="spec-tab__propose-actions">
      <button type="button" className="spec-tab__ghost" disabled={!changes || readOnly || state.busy || !accepted} onClick={discard}>Zahodit</button>
      <button type="button" className="spec-tab__primary" disabled={!!blocked || !subject.trim() || state.busy} onClick={propose}
        data-oh-action="changeset.propose">Navrhnout změnu</button>
    </div>
    {state.text && <p className={`spec-tab__notice spec-tab__notice--${state.tone}`} role="status">{state.text}</p>}
  </section>;
}
