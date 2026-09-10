import { useEffect, useRef, useState } from "react";
import { api } from "./types";
import type {
  AgentBindingCandidate,
  AgentRunDetail,
  AgentRunSummary,
  AgentRunsPage,
  AgentSourceHealth,
} from "./agent-types";

const POLL_MS = 4000;

function useVisiblePolling(fn: () => void, deps: unknown[]) {
  useEffect(() => {
    let alive = true;
    const tick = () => {
      if (alive && !document.hidden) fn();
    };
    tick();
    const timer = setInterval(tick, POLL_MS);
    const onVisible = () => {
      if (!document.hidden) fn();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      alive = false;
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

function StaleBadge({ status }: { status: { reported: string; liveness: string } }) {
  const live = status.liveness;
  const tone =
    live === "last_reported_running_liveness_unverified"
      ? "warn"
      : live === "stale_not_running"
        ? "bad"
        : live.startsWith("reported_by_bridge") || live === "reported_stopped"
          ? "ok"
          : "unknown";
  return (
    <span className={"agent-badge agent-badge-" + tone} title={live}>
      {status.reported} · {live}
    </span>
  );
}

/** Kontrakt pro rodiče: `onOpenNode` je zavolán, když uživatel z detailu běhu naviguje
 * na konkrétní uzel Canvasu (jen čtení, žádné spuštění). Rodič rozhodne, jak přepnout
 * výběr uzlu/pracovního prostoru; tato komponenta netlačí vlastní routing. */
export default function AgentsWorkspace({
  project,
  workspace,
  onOpenNode,
}: {
  project: string;
  workspace: string;
  onOpenNode?: (nodeId: string) => void;
}) {
  const [sources, setSources] = useState<Record<string, AgentSourceHealth>>({});
  const [page, setPage] = useState<AgentRunsPage>({ items: [], nextCursor: null, total: 0 });
  const [unbound, setUnbound] = useState<AgentBindingCandidate[]>([]);
  const [selected, setSelected] = useState<AgentRunSummary | null>(null);
  const [detail, setDetail] = useState<AgentRunDetail | null>(null);
  const [error, setError] = useState("");
  const [bindTarget, setBindTarget] = useState<AgentBindingCandidate | null>(null);
  const [bindNodeId, setBindNodeId] = useState("");
  const [bindConfirmed, setBindConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const selectedRef = useRef<AgentRunSummary | null>(null);
  selectedRef.current = selected;

  useVisiblePolling(() => {
    api<Record<string, AgentSourceHealth>>("/api/agents/sources")
      .then(setSources)
      .catch((e) => setError(String(e)));
    api<AgentRunsPage>("/api/agents/runs?limit=30")
      .then((body) => {
        setPage(body);
        const current = selectedRef.current;
        if (current) {
          const fresh = body.items.find((r) => r.sourceId === current.sourceId && r.runId === current.runId);
          if (fresh) setSelected(fresh);
        }
      })
      .catch((e) => setError(String(e)));
    api<{ items: AgentBindingCandidate[] }>("/api/agents/unbound?limit=30")
      .then((body) => setUnbound(body.items))
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!selected) {
      setDetail(null);
      return;
    }
    let alive = true;
    api<AgentRunDetail>(`/api/agents/runs/${encodeURIComponent(selected.sourceId)}/${encodeURIComponent(selected.runId)}`)
      .then((body) => {
        if (alive) setDetail(body);
      })
      .catch((e) => alive && setError(String(e)));
    return () => {
      alive = false;
    };
  }, [selected]);

  async function confirmBind() {
    if (!bindTarget) return;
    setBusy(true);
    setError("");
    try {
      await api("/api/agents/bindings", {
        project,
        workspace,
        layer: "",
        nodeId: bindNodeId,
        sourceId: bindTarget.sourceId,
        runId: bindTarget.runId,
        sessionId: null,
        expectedRevision: 0,
        confirmed: bindConfirmed,
      });
      setBindTarget(null);
      setBindNodeId("");
      setBindConfirmed(false);
      onOpenNode?.(bindNodeId);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="agents-workspace" aria-label="Agenti">
      <h2>Agenti · skutečné zdroje</h2>
      <div className="agent-sources">
        {Object.entries(sources).map(([id, health]) => (
          <span key={id} className={"agent-badge " + (health.available ? "agent-badge-ok" : "agent-badge-bad")}>
            {id}: {health.available ? (health.status ?? "dostupný") : (health.error ?? "nedostupný")}
          </span>
        ))}
      </div>
      {error && (
        <p role="alert" className="agent-error">
          {error}
        </p>
      )}
      <div className="agents-columns">
        <div className="agent-run-list">
          <h3>Běhy ({page.total})</h3>
          {page.items.length === 0 && <p>Žádné běhy z nakonfigurovaných zdrojů.</p>}
          {page.items.map((run) => (
            <button
              key={run.sourceId + "/" + run.runId}
              className={"agent-run-item" + (selected?.runId === run.runId && selected.sourceId === run.sourceId ? " selected" : "")}
              onClick={() => setSelected(run)}
              aria-pressed={selected?.runId === run.runId && selected.sourceId === run.sourceId}
            >
              <strong>{run.runId}</strong> <small>{run.sourceId}</small>
              <StaleBadge status={run.status} />
            </button>
          ))}
          {unbound.length > 0 && (
            <div className="agent-unbound">
              <h4>Nepřiřazené běhy</h4>
              {unbound.map((candidate) => (
                <div key={candidate.sourceId + "/" + candidate.runId} className="agent-unbound-item">
                  <code>
                    {candidate.sourceId}/{candidate.runId}
                  </code>
                  <button onClick={() => setBindTarget(candidate)}>Přiřadit k uzlu</button>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="agent-detail">
          {!detail && <p>Vyberte běh pro detail.</p>}
          {detail && (
            <>
              <h3>
                {detail.sourceId} / {detail.runId}
              </h3>
              <p>
                <StaleBadge status={detail.status} /> · seq {detail.lastEventSeq ?? "—"} · zdrojový čas{" "}
                {detail.sourceTimestamp ?? "neznámý"}
              </p>
              {detail.missing.length > 0 && (
                <p className="agent-missing">Harness neposkytuje: {detail.missing.join(", ")}</p>
              )}
              {detail.brain && (
                <dl className="agent-brain">
                  <dt>Zadání/prompt</dt>
                  <dd>{detail.brain.promptSpec}</dd>
                  <dt>Kontextový snímek</dt>
                  <dd>{detail.brain.contextSnapshot}</dd>
                  <dt>Verifikace</dt>
                  <dd>{detail.brain.verifierArtifact}</dd>
                  <dt>Iterace / rozpočet</dt>
                  <dd>
                    {detail.brain.iterations} / {detail.brain.maxIterations} · {detail.brain.budget}
                  </dd>
                  <dt>Důvod ukončení</dt>
                  <dd>{detail.brain.doneReason ?? "neznámý"}</dd>
                </dl>
              )}
              <h4>Bezpečný náhled akcí (bez interního uvažování)</h4>
              <ol className="agent-timeline">
                {detail.preview.map((event, index) => (
                  <li key={index}>
                    <em>{event.kind}</em>
                    {event.content?.map((block, blockIndex) => (
                      <div key={blockIndex} className="agent-block">
                        {"text" in block && block.text}
                        {"name" in block && block.name && <code>{block.name}</code>}
                        {"content" in block && block.content}
                      </div>
                    ))}
                  </li>
                ))}
              </ol>
            </>
          )}
        </div>
      </div>
      {bindTarget && (
        <div role="dialog" aria-label="Přiřazení běhu k uzlu" className="agent-bind-dialog">
          <p>
            Přiřadit {bindTarget.sourceId}/{bindTarget.runId} k uzlu v {project}/{workspace}. Vazba je jen čtení; nic
            nespouští ani nezastavuje.
          </p>
          <label className="field">
            ID uzlu
            <input value={bindNodeId} onChange={(e) => setBindNodeId(e.target.value)} />
          </label>
          <label className="check">
            <input type="checkbox" checked={bindConfirmed} onChange={(e) => setBindConfirmed(e.target.checked)} />
            Potvrzuji přiřazení k tomuto uzlu
          </label>
          <button disabled={busy} onClick={() => setBindTarget(null)}>
            Zrušit
          </button>
          <button disabled={busy || !bindConfirmed || !bindNodeId} onClick={confirmBind}>
            Potvrdit vazbu
          </button>
        </div>
      )}
    </section>
  );
}
