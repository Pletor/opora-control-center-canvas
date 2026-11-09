import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";

type Intent = { id: string; digest: string; operation: Record<string, unknown>; reason: string; by: { kind: string; name: string };
  preimage: { tables: Record<string, Record<string, unknown>[]> };
  decision: { status: string; response: { status?: string } | null } | null };
const ROOT = "/api/brief-vault/reviews";
const LABELS: Record<string, string> = { op: "Operace", title: "Název", text: "Úplný text", note: "Důvod", fragmentId: "Fragment",
  expectedRevision: "Očekávaná revize", revision: "Revize", fragmentIds: "Fragmenty", mvp: "Zařazení MVP", payload: "Navržený obsah",
  gate: "Brána", value: "Nová hodnota", answer: "Odpověď", verdict: "Verdikt", evidence: "Důkazy", discipline: "Disciplína",
  scopeNodeId: "Rozsah karty", parentId: "Rodič", parts: "Rozdělené části", question: "Otázka", status: "Stav", round: "Kolo" };

export function PinnedFragments({ operation, records }: { operation: Record<string, unknown>; records: Record<string, unknown>[] }) {
  const latest = new Map<string, Record<string, unknown>>();
  for (const row of records) {
    const id = String(row.fragment_id);
    if (!latest.has(id) || Number(row.revision) > Number(latest.get(id)!.revision)) latest.set(id, row);
  }
  const selected = new Set([operation.fragmentId, operation.parentId, operation.duelId, operation.fromDuel,
    ...(Array.isArray(operation.fragmentIds) ? operation.fragmentIds : [])].filter(value => typeof value === "string") as string[]);
  let added = true;
  while (added) {
    added = false;
    for (const [id, row] of latest) if (selected.has(String(row.parent_id)) && !selected.has(id)) { selected.add(id); added = true; }
  }
  const rows = [...latest.values()].filter(row => selected.has(String(row.fragment_id)));
  if (!rows.length) return null;
  return <section><h3>Dotčené podklady před změnou</h3>{rows.map(row => {
    let gates: unknown = null;
    if (typeof row.gates === "string") { try { gates = JSON.parse(row.gates); } catch { gates = row.gates; } }
    return <article key={String(row.fragment_id)}><h4>{String(row.title)} · revize {String(row.revision)}</h4>
      <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{String(row.text ?? "")}</p>
      <p><code>{String(row.fragment_id)}</code></p>
      {gates !== null && <details><summary>Připnuté brány a uložený plán</summary><OperationFields value={gates} /></details>}
    </article>;
  })}</section>;
}

export function OperationFields({ value }: { value: unknown }) {
  if (Array.isArray(value)) return <ol>{value.map((item, index) => <li key={index}><OperationFields value={item} /></li>)}</ol>;
  if (value !== null && typeof value === "object") return <dl>{Object.entries(value).map(([key, item]) => <div key={key}>
    <dt>{LABELS[key] ?? key}</dt><dd><OperationFields value={item} /></dd></div>)}</dl>;
  return <span style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{value === null ? "—" : String(value)}</span>;
}

export default function VaultOperationReview({ project, workspace }: { project: string; workspace: string }) {
  const params = new URLSearchParams(location.search);
  const id = params.get("project") === project && params.get("workspace") === workspace ? params.get("vaultReview") : null;
  const key = JSON.stringify([project, workspace, id]);
  const active = useRef(key), generation = useRef(0);
  if (active.current !== key) { active.current = key; generation.current++; }
  const [attempt, setAttempt] = useState(0), [checked, setChecked] = useState("");
  const [state, setState] = useState<{ key: string; item: Intent | null; busy: boolean; error: string }>({ key, item: null, busy: false, error: "" });
  const shown = state.key === key ? state : { key, item: null, busy: true, error: "" };
  useEffect(() => {
    const run = ++generation.current;
    setChecked("");
    setState({ key, item: null, busy: !!id, error: "" });
    if (id) api<Intent>(`${ROOT}/${encodeURIComponent(id)}?${new URLSearchParams({ project, workspace })}`)
      .then(item => { if (generation.current === run) setState({ key, item, busy: false, error: "" }); })
      .catch(error => { if (generation.current === run) setState({ key, item: null, busy: false, error: String(error) }); });
    return () => { generation.current++; };
  }, [key, id, project, workspace, attempt]);
  if (!id) return null;
  const item = shown.item;
  const pending = item && !item.decision;
  async function decide(action: "accept" | "reject") {
    if (!item || !pending || shown.busy || shown.error) return;
    const run = generation.current;
    setState({ ...shown, busy: true, error: "" });
    try {
      await api(`${ROOT}/${encodeURIComponent(item.id)}/${action}`, { project, workspace, digest: item.digest });
      if (generation.current === run) setAttempt(value => value + 1);
    } catch (error) {
      if (generation.current === run) setState({ ...shown, busy: false, error: String(error) + " Obnovte uložený výsledek před dalším pokusem." });
    }
  }
  const close = () => { const url = new URL(location.href); url.searchParams.delete("vaultReview"); location.assign(url); };
  return <div className="modal-backdrop"><section className="modal" role="dialog" aria-label="Posouzení operace schránky" style={{ width: "min(1000px, calc(100vw - 48px))", maxWidth: 1000, maxHeight: "90vh", overflow: "auto" }}>
    <h2>Posouzení operace schránky</h2><button type="button" onClick={close}>Zavřít</button>
    <p>Agent připravil přesné zadání operace. Pouze vaše výslovné potvrzení provede nativní změnu; nejde o přijetí realizačního plánu.</p>
    {shown.error && <p role="alert">{shown.error}</p>}{shown.busy && <p role="status">Načítám…</p>}
    <button type="button" disabled={shown.busy} onClick={() => setAttempt(value => value + 1)}>Obnovit uložený výsledek</button>
    {item && <><p>Navrhl {item.by.name} · <code>{item.id}</code></p><p>{item.reason}</p>
      <h3>Přesně navržená změna</h3><OperationFields value={item.operation} />
      <PinnedFragments operation={item.operation} records={item.preimage.tables.brief_fragment_revisions ?? []} />
      <details><summary>Připnuté podklady a historie schránky</summary>{Object.entries(item.preimage.tables).map(([table, rows]) =>
        <details key={table}><summary>{table} · {rows.length} záznamů</summary><OperationFields value={rows} /></details>)}</details>
      {item.decision ? <p role="status">{item.decision.status === "pending" ? "Výsledek je nejistý. Operaci neopakujte; je nutné ověřit nativní stav." : item.decision.response?.status === "accepted" ? "Operace potvrzena a nativně provedena." : "Operace zamítnuta."}</p>
        : <><label><input type="checkbox" checked={checked === item.id} onChange={event => setChecked(event.target.checked ? item.id : "")} />Zkontroloval/a jsem přesný obsah a rozsah této operace.</label>
          <button type="button" disabled={shown.busy || !!shown.error || checked !== item.id} onClick={() => void decide("accept")}>Provést tuto operaci</button>
          <button type="button" disabled={shown.busy || !!shown.error} onClick={() => void decide("reject")}>Zamítnout tuto operaci</button></>}
    </>}
  </section></div>;
}
