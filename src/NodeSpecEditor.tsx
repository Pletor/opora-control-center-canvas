import { useEffect, useRef, useState } from "react";
import { api, type NodeSpec, type SpecFields } from "./types";

const drafts = new Map<string, { fields: SpecFields; revision: number }>();
const EMPTY: SpecFields = { goal: "", non_goals: "", acceptance: "" };
const FIELDS: { key: keyof SpecFields; label: string; limit: number }[] = [
  { key: "goal", label: "Cíl práce", limit: 4000 },
  { key: "non_goals", label: "Co není součástí", limit: 8000 },
  { key: "acceptance", label: "Podmínky dokončení", limit: 12000 },
];

function sameFields(a: SpecFields, b: SpecFields) {
  return FIELDS.every(({ key }) => a[key] === b[key]);
}

export default function NodeSpecEditor({ project, workspace, nodeId, disabled }: {
  project: string; workspace: string; nodeId: string; disabled: boolean;
}) {
  const key = JSON.stringify([project, workspace, nodeId]);
  const [baseRevision, setBaseRevision] = useState(0);
  const [stored, setStored] = useState<NodeSpec | null>(null);
  const [fields, setFields] = useState<SpecFields>({ ...EMPTY });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const generation = useRef(0);
  useEffect(() => {
    const ticket = ++generation.current;
    setLoading(true);
    api<NodeSpec>("/api/node-spec?" + new URLSearchParams({ project, workspace, node: nodeId }))
      .then((value) => {
        if (ticket !== generation.current) return;
        const draft = drafts.get(key);
        setStored(value);
        if (draft && !value.readOnly && !sameFields(draft.fields, value.fields)) {
          setFields(draft.fields); setBaseRevision(draft.revision);
          setError(draft.revision !== value.revision ? "Konflikt: uložená revize se změnila. Váš rozepsaný text je zachován." : "");
        } else {
          drafts.delete(key); setFields(value.fields); setBaseRevision(value.revision); setError("");
        }
      })
      .catch((e) => { if (ticket === generation.current) setError(String(e)); })
      .finally(() => { if (ticket === generation.current) setLoading(false); });
    return () => { generation.current++; };
  }, [project, workspace, nodeId, reload]);
  const dirty = !!stored && !sameFields(fields, stored.fields);
  async function save() {
    if (!stored || stored.readOnly || loading || saving || disabled) return;
    const ticket = generation.current;
    setSaving(true); setError("");
    try {
      const value = await api<NodeSpec>("/api/node-spec", {
        project, workspace, node: nodeId, expected_revision: baseRevision, fields,
      });
      const draft = drafts.get(key);
      if (draft && draft.revision === baseRevision && sameFields(draft.fields, fields)) drafts.delete(key);
      if (ticket === generation.current) { setStored(value); setFields(value.fields); setBaseRevision(value.revision); }
    } catch (e) {
      if (ticket === generation.current) setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (ticket === generation.current) setSaving(false);
    }
  }
  return <section className="node-spec" aria-label="Zadání uzlu">
    <h3>Zadání pro práci</h3>
    <p className="spec-state" data-testid="spec-status" role="status">
      {loading ? "Načítám zadání…" : saving ? "Ukládám zadání…" : dirty ? "Neuložené změny" : stored?.revision ? `Uloženo · verze ${stored.revision}` : "Zadání zatím nebylo uloženo"}
    </p>
    {FIELDS.map(({ key, label, limit }) => <label className="field" key={key}>
      {label}
      <textarea aria-label={label} rows={3} maxLength={limit}
        value={fields[key]} disabled={loading || saving || disabled || !stored}
        readOnly={stored?.readOnly ?? true}
        onChange={(e) => {
          const next = { ...fields, [key]: e.target.value };
          drafts.set(JSON.stringify([project, workspace, nodeId]), { fields: next, revision: baseRevision });
          setFields(next);
        }} />
    </label>)}
    {stored && !stored.readOnly && <button className="primary wide" disabled={!dirty || loading || saving || disabled} onClick={save}>Uložit zadání</button>}
    {error && <div className="spec-error" role="alert"><p>{error}</p>
      <button disabled={saving || loading} onClick={() => { drafts.delete(key); setReload(reload + 1); }}>Zahodit rozepsané a načíst uložené</button>
    </div>}
    <p className="muted spec-source">{stored?.source}</p>
    {dirty && <small>Neuložený text zatím není trvalé zadání. Před obnovením stránky jej uložte.</small>}
  </section>;
}
