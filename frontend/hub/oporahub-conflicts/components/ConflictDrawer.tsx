import { useEffect, useState } from "react";
import { api, ApiError } from "@/shared/types/logic/types";
import { useHubRead } from "@/hub/oporahub-mirror/logic/use-hub-read";
import JsonMirror from "@/hub/oporahub-mirror/components/JsonMirror";
import { ToneChip } from "@/hub/oporahub-health/components/HealthMark";
import { conflictsUrl, KIND_LABEL, parseConflicts, RUN_URL, STATUS_GLYPH, STATUS_LABEL, type StatusFilter } from "../logic/conflicts";
import ConflictFields from "./ConflictFields";
import "../styles/oporahub-conflicts.css";

const TONE = { open: "warn", resolved: "ok", obsolete: "gap" } as const;

/** Konflikty auto-rebase: seznam vlevo, vybraný konflikt s poli base/ours/theirs a řešením vpravo. */
export default function ConflictDrawer({ project, workspace, requestedId, onResolved }: {
  project: string; workspace: string; requestedId?: string; onResolved: () => void;
}) {
  const [filter, setFilter] = useState<StatusFilter>("open");
  const read = useHubRead(project && workspace ? conflictsUrl(project, workspace, filter) : null, parseConflicts);
  const [selected, setSelected] = useState(requestedId ?? "");
  const [run, setRun] = useState({ busy: false, message: "" });
  const items = read.data?.items ?? [];
  useEffect(() => {
    if (items.length && !items.some(item => item.id === selected)) setSelected(items.find(item => item.id === requestedId)?.id ?? items[0].id);
  }, [items, selected, requestedId]);
  const current = items.find(item => item.id === selected) ?? null;
  async function runNow() {
    setRun({ busy: true, message: "" });
    try { await api(RUN_URL, { project, workspace }); setRun({ busy: false, message: "Průchod auto-rebase proběhl." }); read.reload(); onResolved(); }
    catch (error) { setRun({ busy: false, message: error instanceof ApiError || error instanceof Error ? error.message : "Průchod se nezdařil." }); }
  }
  return <div className="oporahub-conflicts" data-oh-view="conflicts" data-oh-accepted-head={read.data?.acceptedHead ?? ""}>
    <JsonMirror id="oh-auto-rebase-conflicts" value={read.data} />
    <header className="oporahub-conflicts__head">
      <p className="oporahub-conflicts__note">Server převádí zastaralé návrhy sám. Konflikt vzniká jen tam, kde návrh i aktuální hlava změnily
        <b> stejné pole</b> jinak (base ≠ ours ≠ theirs). Řešením je běžný nový návrh nad aktuální hlavou; přijímá ho člověk.</p>
      <div className="oporahub-conflicts__tools">
        <label className="oporahub-conflicts__filter">Stav
          <select value={filter} onChange={event => setFilter(event.target.value as StatusFilter)}>
            <option value="open">otevřené</option><option value="all">všechny</option>
          </select>
        </label>
        <button type="button" className="oporahub-conflicts__button" disabled={run.busy || !project} onClick={() => void runNow()}>
          {run.busy ? "Spouštím…" : "Spustit auto-rebase teď"}</button>
        <button type="button" className="oporahub-conflicts__button" onClick={read.reload}>Obnovit</button>
      </div>
      {run.message && <p className="oporahub-conflicts__note" role="status">{run.message}</p>}
    </header>
    {read.data && !read.data.enabled && <p className="oporahub-conflicts__warning" role="status">
      ◌ Automatický rebase je vypnutý (<code>OPORA_AUTO_REBASE=0</code>); zastaralé návrhy převádí člověk nebo agent výslovným rebase.</p>}
    {read.error && <p className="oporahub-conflicts__warning" role="alert">{read.error}</p>}
    {read.busy && !read.data && <p className="oporahub-conflicts__note" role="status">Načítám konflikty…</p>}
    {read.data && !items.length && <p className="oporahub-conflicts__empty">✓ {filter === "open" ? "Žádný otevřený konflikt." : "Žádné konflikty."}</p>}
    {!!items.length && <div className="oporahub-conflicts__layout">
      <ul className="oporahub-conflicts__list" aria-label="Konflikty" data-oh-list="conflicts">
        {items.map(item => <li key={item.id}>
          <button type="button" className={`oporahub-conflicts__item${item.id === selected ? " oporahub-conflicts__item--selected" : ""}`}
            aria-pressed={item.id === selected} onClick={() => setSelected(item.id)}
            data-oh-conflict={item.id} data-oh-conflict-status={item.status} data-oh-proposal={item.proposalId} data-oh-proposal-kind={item.proposalKind}>
            <span className="oporahub-conflicts__item-title">{KIND_LABEL[item.proposalKind] ?? item.proposalKind} · <code>{item.proposalId.slice(0, 14)}</code></span>
            <span className="oporahub-conflicts__item-meta">
              <ToneChip tone={TONE[item.status]}>{STATUS_GLYPH[item.status]} {STATUS_LABEL[item.status]}</ToneChip>
              {item.items.length} polí · {item.createdAt.slice(0, 16).replace("T", " ")}</span>
          </button>
        </li>)}
      </ul>
      {current && <ConflictFields key={current.id} conflict={current} project={project} workspace={workspace}
        onResolved={() => { read.reload(); onResolved(); }} />}
    </div>}
  </div>;
}
