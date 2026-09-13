import { useEffect, useRef, useState } from "react";
import { api } from "@/types";
import BlockOutline, { type LinkTarget } from "@/BlockOutline";
import { clearPendingEdit, editScope, readPendingEdit, usePendingFlush, writePendingEdit } from "@/use-pending-edits";
import "@/text-workspace.css";
import "@/natural-canvas.css";

type Snapshot = { revision: number; text: string; readOnly: boolean; available: boolean };
type Draft = Snapshot & { dirty: boolean };
export const AUTOSAVE_MS = 700;

export default function NodeTextEditor({
  project,
  workspace,
  node,
  targets = [],
  onOpenNode,
  onAgentTask,
  onSaved,
}: {
  project: string;
  workspace: string;
  node: string;
  targets?: LinkTarget[];
  onOpenNode?: (nodeId: string) => void;
  onAgentTask?: (text: string) => void;
  onSaved?: () => void;
}) {
  const key = editScope("node-text", [project, workspace, node]);
  const [form, setForm] = useState<Draft | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  const timer = useRef<number | null>(null);
  const latest = useRef<Draft | null>(null);
  const lifetime = useRef<object | null>(null);
  latest.current = form;
  useEffect(() => {
    lifetime.current = {};
    let alive = true; setForm(null); setError("");
    api<Snapshot>("/api/node-text?" + new URLSearchParams({ project, workspace, node })).then(value => {
      if (!alive) return;
      const cached = readPendingEdit(key);
      const kept = cached && cached.text !== value.text;
      if (!kept) clearPendingEdit(key);
      setForm(kept ? { ...value, text: cached.text, revision: cached.revision, dirty: true } : { ...value, dirty: false });
      if (kept && cached.revision !== value.revision) setError("Konflikt: uložená revize se změnila. Rozepsaný text je zachovaný.");
    }).catch(e => { if (alive) setError(String(e)); });
    return () => { alive = false; lifetime.current = null; };
  }, [key, reload]);
  // Rozepsaný text nesmí zmizet přechodem jinam: čekající uložení se dokončí hned.
  usePendingFlush(key, () => { if (timer.current) { window.clearTimeout(timer.current); timer.current = null; void save(latest.current); } });
  async function save(source?: Draft | null) {
    const value = source ?? form;
    if (!value || busy || value.readOnly || !value.available || !value.dirty) return;
    const owner = lifetime.current;
    if (timer.current) { window.clearTimeout(timer.current); timer.current = null; }
    setBusy(true); setError("");
    try {
      const saved = await api<Snapshot>("/api/node-text", { project, workspace, node, expected_revision: value.revision, text: value.text });
      // Starý editor smí potvrdit jen svůj snapshot, ne měnit novou instanci či její draft.
      if (!owner || lifetime.current !== owner) { clearPendingEdit(key, value); return; }
      onSaved?.();
      // Během ukládání se mohlo dopsat víc; odpověď nesmí přepsat novější rozepsaný text.
      const typing = latest.current;
      if (typing && typing.text !== value.text) {
        const kept = { ...saved, text: typing.text, dirty: true };
        writePendingEdit(key, { text: kept.text, revision: kept.revision }); setForm(kept);
        timer.current = window.setTimeout(() => { timer.current = null; void save(latest.current); }, AUTOSAVE_MS);
      } else { clearPendingEdit(key, value); setForm({ ...saved, dirty: false }); }
    } catch (e) { if (owner && lifetime.current === owner) setError(e instanceof Error ? e.message : String(e)); }
    finally { if (owner && lifetime.current === owner) setBusy(false); }
  }
  /** Bloky se ukládají samy se zpožděním; zdrojový text zůstává na ruční uložení. */
  function edit(text: string, autosave: boolean) {
    if (!form || form.readOnly || !form.available) return;
    const next = { ...form, text, dirty: true };
    writePendingEdit(key, { text, revision: next.revision }); setForm(next);
    if (!autosave) return;
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => { timer.current = null; void save(latest.current); }, AUTOSAVE_MS);
  }
  const status = !form ? "Načítám text…" : !form.available ? "Text mainu není importován." : busy ? "Ukládám…" : error ? "Neuloženo · chyba" : form.dirty ? "Neuložený text" : `Uloženo · verze ${form.revision}`;
  return <section className="node-text-editor" aria-label="Dokument uzlu">
    {error && <div role="alert">{error}{form && <button disabled={busy} onClick={() => { clearPendingEdit(key); setError(""); setReload(x => x + 1); }}>Zahodit rozepsaný text a načíst uložený</button>}</div>}
    {form && <BlockOutline key={key + reload} value={form.text} readOnly={form.readOnly || !form.available} targets={targets} label="Bloky uzlu" testId="node-blocks" onChange={text => edit(text, true)} onOpenNode={onOpenNode} onAgentTask={onAgentTask} />}
    <details className="source-text" open>
      <summary>Zdrojový text (ruční uložení, Ctrl+S)</summary>
      <label className="field">Text uzlu<textarea aria-label="Text uzlu" rows={6} maxLength={64000} disabled={!form || busy} readOnly={form?.readOnly || !form?.available} value={form?.text ?? ""} placeholder="Pište odstavce, poznámky a souvislosti…" onChange={e => edit(e.target.value, false)} onKeyDown={e => { if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); void save(); } }} /></label>
    </details>
    <div className="text-actions"><span data-testid="text-status" role="status">{status}</span>{form?.available && !form.readOnly && <button disabled={busy || !form.dirty} onClick={() => save()}>Uložit text</button>}</div>
  </section>;
}
