import { useEffect, useRef, useState } from "react";
import { api } from "@/types";
import { clearPendingEdit, editScope, readPendingEdit, writePendingEdit } from "@/use-pending-edits";

export type DocumentFields = { purpose: string; goal: string; architecture: string; technologies: string; notes: string; requirements: string };
export type WorkspaceDocument = { revision: number; settingsRevision: number | null; fields: DocumentFields; nodeId: string | null; status: "missing" | "documented" | "stale"; savedAt: string | null; changeDetection: string };
const pendingValue = (document: WorkspaceDocument) => ({ text: JSON.stringify({ fields: document.fields, settingsRevision: document.settingsRevision }), revision: document.revision });
const labels: [keyof DocumentFields, string][] = [["purpose", "Podstata"], ["goal", "Cíl"], ["architecture", "Hlavní architektura"], ["technologies", "Technologie"], ["notes", "Teorie a poznámky"], ["requirements", "Požadavky a odkazy na důkazy"]];

/** Dokumentace je oddělená od kódu; draft používá stávající ochranu editací. */
export default function WorkspaceDocumentEditor({ project, workspace, path }: { project: string; workspace: string; path: string }) {
  const scope = editScope("workspace-document", [project, workspace, path]);
  const [document, setDocument] = useState<WorkspaceDocument | null>(null);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  const generation = useRef(0);
  useEffect(() => {
    const ticket = ++generation.current;
    setDocument(null); setError(""); setDirty(false);
    api<WorkspaceDocument>("/api/workspace/document?" + new URLSearchParams({ project, workspace, path }))
      .then((saved) => {
        if (ticket !== generation.current) return;
        const pending = readPendingEdit(scope);
        let fields = saved.fields;
        let settingsRevision = saved.settingsRevision;
        let revision = saved.revision;
        if (pending) {
          try {
            const parsed = JSON.parse(pending.text);
            const candidate = parsed.fields ?? parsed;
            if (labels.every(([key]) => typeof candidate[key] === "string")) {
              fields = candidate; setDirty(true); revision = pending.revision;
              settingsRevision = path ? null : Number.isInteger(parsed.settingsRevision) ? parsed.settingsRevision : -1;
              if (saved.revision !== pending.revision || saved.settingsRevision !== settingsRevision) setError("Dokumentace nebo cíl se změnil; rozepsaný text je zachovaný. Před uložením porovnejte změny.");
            }
          } catch { setError("Rozepsaná dokumentace má neplatný formát; uložený obsah je dostupný."); }
        }
        setDocument({ ...saved, fields, revision, settingsRevision });
      }).catch((e) => { if (ticket === generation.current) setError(String(e)); });
    return () => { generation.current++; };
  }, [project, workspace, path, scope, reload]);
  function change(key: keyof DocumentFields, value: string) {
    if (!document) return;
    const next = { ...document, fields: { ...document.fields, [key]: value } };
    writePendingEdit(scope, pendingValue(next));
    setDocument(next); setDirty(true);
  }
  async function save() {
    if (!document || busy || !dirty) return;
    const ticket = generation.current;
    const pending = pendingValue(document);
    setBusy(true); setError("");
    try {
      const saved = await api<WorkspaceDocument>("/api/workspace/document", { project, workspace, path,
        expectedRevision: document.revision, fields: document.fields, nodeId: document.nodeId,
        ...(path ? {} : { expectedSettingsRevision: document.settingsRevision }) });
      clearPendingEdit(scope, pending);
      if (ticket === generation.current) { setDocument(saved); setDirty(false); }
    } catch (e) { if (ticket === generation.current) setError(String(e)); }
    finally { if (ticket === generation.current) setBusy(false); }
  }
  return <section className="workspace-document" aria-label="Dokumentace projektu">
    <header><div className="eyebrow">PROJEKT / DOKUMENTACE NAD KÓDEM</div><h1>{path || "Podstata a architektura"}</h1>
      <p className="muted">Kód zůstává ve zdrojových souborech. Tady tvoříte teorii, záměr a požadavky.</p></header>
    {error && <div className="error" role="alert">{error}<button disabled={busy} onClick={() => {
      if (window.confirm("Zahodit rozepsanou dokumentaci a načíst uloženou verzi?")) { clearPendingEdit(scope); setReload((v) => v + 1); }
    }}>Zahodit rozepsané a obnovit</button></div>}
    {document ? <form onSubmit={(e) => { e.preventDefault(); save(); }}>
      {document.status === "stale" && <p className="warn-text">Metadata zdroje se od uložení změnila. Ověřte platnost dokumentace.</p>}
      <div className="document-fields">{labels.map(([key, label]) => <label className="field" key={key}>{label}
        <textarea aria-label={label} rows={key === "technologies" ? 2 : 4} maxLength={!path && key === "goal" ? 4000 : 16000}
          disabled={busy} value={document.fields[key]} onChange={(e) => change(key, e.target.value)} />
      </label>)}</div>
      <p className="muted">Text požadavku ani vložený odkaz není automaticky ověřený důkaz splnění.</p>
      <footer className="document-save"><span role="status" data-testid="document-status">{busy ? "Ukládám…" : dirty ? "Rozepsáno · zachováno při přepnutí" : document.revision ? `Uloženo · verze ${document.revision}` : "Zatím bez dokumentace"}</span>
        <button className="primary" disabled={busy || !dirty}>Uložit dokumentaci</button></footer>
    </form> : !error && <p role="status">Načítám dokumentaci…</p>}
  </section>;
}
