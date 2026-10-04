import { useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import type { NodeBrief } from "@/shared/desktop-state/logic/types";
import { asRecord, parseResult, resultTemplate, verifyResult, type AcceptedResult, type ResultHistory } from "../logic/handoff";

export default function ResultSubmission({ brief, project, workspace, nodeId, onSaved }: {
  brief: NodeBrief; project: string; workspace: string; nodeId: string; onSaved: () => void;
}) {
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [accepted, setAccepted] = useState<AcceptedResult | null>(null);
  const [verified, setVerified] = useState<AcceptedResult | null>(null);
  const lock = useRef(false);
  const readOnly = !asRecord(brief.outputContract).request;
  const query = new URLSearchParams({ project, workspace, nodeId });

  async function readback(value: AcceptedResult) {
    const history = await api<ResultHistory>(`/api/desktop-v3/agent-results?${query}`);
    setVerified(verifyResult(history, value));
  }
  async function submit() {
    if (lock.current || readOnly || accepted) return;
    lock.current = true; setBusy(true); setError("");
    try {
      const payload = parseResult(draft, { project, workspace, nodeId });
      if (payload.contextVersion !== brief.contextVersion) throw new Error("Výsledek odkazuje na jinou verzi kontextu než načtené zadání. Původní verzi nepřepisujte; ověřte změny zadání.");
      const saved = await api<{ acceptedResult: AcceptedResult }>("/api/desktop-v3/agent-output", payload);
      setAccepted(saved.acceptedResult);
      onSaved();
      await readback(saved.acceptedResult);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { lock.current = false; setBusy(false); }
  }
  async function retryReadback() {
    if (!accepted || lock.current) return;
    lock.current = true; setBusy(true); setError("");
    try { await readback(accepted); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { lock.current = false; setBusy(false); }
  }
  return <details className="handoff__section"><summary>Vrátit výsledek agenta</summary>
    <p>Vložte celý JSON požadavek podle kontraktu v předání. Obsahuje autora, výsledek a původní verzi zadání. Chyba ponechá text beze změny.</p>
    {!draft && <button type="button" disabled={readOnly || busy} onClick={() => setDraft(resultTemplate(brief))}>Vložit šablonu výsledku</button>}
    <label className="field">JSON výsledku<textarea aria-label="JSON výsledku agenta" rows={12} value={draft} readOnly={busy || !!accepted} onChange={(event) => setDraft(event.target.value)} /></label>
    {readOnly && <p>Tento kontext nepovoluje zápis výsledku. Otevřete neuzavřenou kartu v pracovním prostoru.</p>}
    {!accepted && <button type="button" disabled={readOnly || busy || !draft.trim()} onClick={() => void submit()}>Uložit výsledek k původnímu zadání</button>}
    {error && <p role="alert">{error}</p>}
    {accepted && !verified && <><p>Server přijal výsledek {accepted.id}; čeká zpětné ověření.</p><button type="button" disabled={busy} onClick={() => void retryReadback()}>Ověřit uložený výsledek</button></>}
    {verified && <div role="status"><p>Uložení výsledku zpětně ověřeno · {verified.agent} · {verified.createdAt}</p><p>Jde o hlášení agenta; testy a dokončení vyžadují vlastní ověření.</p><p>Verze zadání: <code>{verified.contextVersion}</code></p><details><summary>Uložený výsledek</summary><pre>{JSON.stringify(verified.output, null, 2)}</pre></details></div>}
  </details>;
}
