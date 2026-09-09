import { useEffect, useState } from "react";
import { api } from "./types";
import "./text-workspace.css";

type Snapshot = { revision: number; text: string; readOnly: boolean; available: boolean };
type Draft = Snapshot & { dirty: boolean };
const drafts = new Map<string, Draft>();

export default function NodeTextEditor({ project, workspace, node }: { project: string; workspace: string; node: string }) {
  const key = JSON.stringify([project, workspace, node]);
  const [form, setForm] = useState<Draft | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let alive = true; setForm(null); setError("");
    api<Snapshot>("/api/node-text?" + new URLSearchParams({ project, workspace, node })).then(value => {
      if (!alive) return;
      const cached = drafts.get(key);
      setForm(cached?.dirty ? { ...cached, readOnly: value.readOnly, available: value.available } : { ...value, dirty: false });
      if (cached?.dirty && cached.revision !== value.revision) setError("Konflikt: uložená revize se změnila. Rozepsaný text je zachovaný.");
    }).catch(e => { if (alive) setError(String(e)); });
    return () => { alive = false; };
  }, [key, reload]);
  async function save() {
    if (!form || busy || form.readOnly || !form.available) return;
    setBusy(true); setError("");
    try {
      const value = await api<Snapshot>("/api/node-text", { project, workspace, node, expected_revision: form.revision, text: form.text });
      drafts.delete(key); setForm({ ...value, dirty: false });
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  return <section className="node-text-editor" aria-label="Dokument uzlu">
    {error && <div role="alert">{error}{form && <button disabled={busy} onClick={() => { drafts.delete(key); setReload(x => x + 1); }}>Zahodit rozepsaný text a načíst uložený</button>}</div>}
    <label className="field">Text uzlu<textarea aria-label="Text uzlu" rows={6} maxLength={64000} disabled={!form || busy} readOnly={form?.readOnly || !form?.available} value={form?.text ?? ""} placeholder="Pište odstavce, poznámky a souvislosti…" onChange={e => { if (!form) return; const next = { ...form, text: e.target.value, dirty: true }; drafts.set(key, next); setForm(next); }} onKeyDown={e => { if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); save(); } }} /></label>
    <div className="text-actions"><span data-testid="text-status" role="status">{!form ? "Načítám text…" : !form.available ? "Text mainu není importován." : busy ? "Ukládám…" : form.dirty ? "Neuložený text" : `Uloženo · verze ${form.revision}`}</span>{form?.available && !form.readOnly && <button disabled={busy || !form.dirty} onClick={save}>Uložit text</button>}</div>
  </section>;
}
