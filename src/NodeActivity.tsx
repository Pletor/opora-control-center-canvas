import { useEffect, useState } from "react";
import { api } from "./types";
import type { AgentActivityEntry, AgentBinding, AgentBindingCandidate, AgentBindingList } from "./agent-types";

const POLL_MS = 5000;

/** Kontrakt pro rodiče (NodePanel/Board): vloží tuto komponentu do detailu uzlu/sektoru.
 * `onOpenRun` je jediný způsob navigace ven — žádné vlastní přesměrování ani spouštění. */
export default function NodeActivity({
  project,
  workspace,
  nodeId,
  isSector = false,
  onOpenRun,
}: {
  project: string;
  workspace: string;
  nodeId: string;
  isSector?: boolean;
  onOpenRun?: (sourceId: string, runId: string) => void;
}) {
  const [bindings, setBindings] = useState<AgentBindingList>({ revision: 0, items: [] });
  const [sectorItems, setSectorItems] = useState<{ sourceId: string; runId: string }[]>([]);
  const [journal, setJournal] = useState<AgentActivityEntry[]>([]);
  const [candidates, setCandidates] = useState<AgentBindingCandidate[]>([]);
  const [error, setError] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [chosen, setChosen] = useState<AgentBindingCandidate | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    const refresh = () => {
      if (document.hidden) return;
      const params = new URLSearchParams({ project, workspace, nodeId });
      api<AgentBindingList>("/api/agents/bindings?" + params)
        .then((body) => alive && setBindings(body))
        .catch((e) => alive && setError(String(e)));
      api<AgentActivityEntry[]>("/api/agents/activity?" + params)
        .then((body) => alive && setJournal(body))
        .catch((e) => alive && setError(String(e)));
      if (isSector) {
        api<{ items: { sourceId: string; runId: string }[] }>("/api/agents/bindings/sector?" + params)
          .then((body) => alive && setSectorItems(body.items))
          .catch((e) => alive && setError(String(e)));
      }
    };
    refresh();
    const timer = setInterval(refresh, POLL_MS);
    const onVisible = () => {
      if (!document.hidden) refresh();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      alive = false;
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [project, workspace, nodeId, isSector]);

  function openDialog() {
    api<{ items: AgentBindingCandidate[] }>("/api/agents/unbound?limit=30")
      .then((body) => setCandidates(body.items))
      .catch((e) => setError(String(e)));
    setDialogOpen(true);
  }

  async function confirmBind() {
    if (!chosen) return;
    setBusy(true);
    setError("");
    try {
      const updated = await api<AgentBindingList>("/api/agents/bindings", {
        project,
        workspace,
        layer: "",
        nodeId,
        sourceId: chosen.sourceId,
        runId: chosen.runId,
        sessionId: null,
        expectedRevision: bindings.revision,
        confirmed,
      });
      setBindings(updated);
      setDialogOpen(false);
      setChosen(null);
      setConfirmed(false);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="node-activity" aria-label="Aktivita agenta u uzlu">
      {error && (
        <p role="alert" className="agent-error">
          {error}
        </p>
      )}
      <h4>Přiřazené běhy agenta</h4>
      {bindings.items.length === 0 && <p>Žádná vazba na běh agenta.</p>}
      <ul className="agent-binding-list">
        {bindings.items.map((b: AgentBinding) => (
          <li key={b.bindingId}>
            <button className="agent-run-link" onClick={() => onOpenRun?.(b.sourceId, b.runId)}>
              {b.sourceId}/{b.runId}
            </button>
            {b.sessionId && <small> · session {b.sessionId}</small>}
          </li>
        ))}
      </ul>
      <button onClick={openDialog}>Přiřadit další běh</button>
      {isSector && (
        <>
          <h4>Souhrn sektoru (potomci)</h4>
          {sectorItems.length === 0 && <p>Žádná vazba v žádném potomkovi.</p>}
          <ul className="agent-binding-list">
            {sectorItems.map((item) => (
              <li key={item.sourceId + "/" + item.runId}>
                <button className="agent-run-link" onClick={() => onOpenRun?.(item.sourceId, item.runId)}>
                  {item.sourceId}/{item.runId}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      {journal.length > 0 && (
        <>
          <h4>Zachycená aktivita</h4>
          <ul className="agent-journal-list">
            {journal.map((entry) => (
              <li key={entry.entryId}>
                <small>
                  zdroj {entry.sourceTimestamp ?? "?"} · přijato {entry.ingestTimestamp}
                </small>
                <div>{entry.summary}</div>
              </li>
            ))}
          </ul>
        </>
      )}
      {dialogOpen && (
        <div role="dialog" aria-label="Přiřazení běhu k tomuto uzlu" className="agent-bind-dialog">
          <label className="field">
            Nepřiřazený běh
            <select
              value={chosen ? chosen.sourceId + "/" + chosen.runId : ""}
              onChange={(e) => {
                const found = candidates.find((c) => c.sourceId + "/" + c.runId === e.target.value);
                setChosen(found ?? null);
              }}
            >
              <option value="">Vyberte běh</option>
              {candidates.map((c) => (
                <option key={c.sourceId + "/" + c.runId} value={c.sourceId + "/" + c.runId}>
                  {c.sourceId}/{c.runId}
                </option>
              ))}
            </select>
          </label>
          <label className="check">
            <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
            Potvrzuji vazbu na tento uzel
          </label>
          <button disabled={busy} onClick={() => setDialogOpen(false)}>
            Zrušit
          </button>
          <button disabled={busy || !chosen || !confirmed} onClick={confirmBind}>
            Potvrdit vazbu
          </button>
        </div>
      )}
    </section>
  );
}
