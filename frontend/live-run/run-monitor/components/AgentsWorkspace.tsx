import { useEffect, useRef, useState } from "react";
import { api, type View } from "@/shared/types/logic/types";
import LiveRunDetail, { type LivePane } from "@/live-run/run-monitor/components/LiveRunDetail";
import type {
  AgentBindingCandidate,
  AgentRunDetail,
  AgentRunSummary,
  AgentRunsPage,
  AgentSourceHealth,
} from "@/live-run/run-monitor/logic/agent-types";

const POLL_MS = 4000;

/** `fn` dostane `isCurrent()`, aby libovolný `.then` mohl ověřit, že tento
 * polling cyklus ještě patří k aktuálnímu scope/stránce (generace/disposal
 * guard) — chrání proti pozdní odpovědi ze staré stránky/scope přepsání
 * novějšího stavu. `inFlight` navíc brání překryvu dvou cyklů nad sebou. */
function useVisiblePolling(fn: (isCurrent: () => boolean) => unknown, deps: unknown[]) {
  useEffect(() => {
    let alive = true;
    let inFlight = false;
    const tick = () => {
      if (!alive || document.hidden || inFlight) return;
      inFlight = true;
      Promise.resolve(fn(() => alive)).finally(() => {
        inFlight = false;
      });
    };
    tick();
    const timer = setInterval(tick, POLL_MS);
    const onVisible = () => {
      if (!document.hidden) tick();
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
  focusRun,
}: {
  project: string;
  workspace: string;
  onOpenNode?: (nodeId: string) => void;
  /** Běh vyžádaný z detailu uzlu: po načtení seznamu se vybere, žádný další fetch navíc. */
  focusRun?: { sourceId: string; runId: string } | null;
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
  const [pane, setPane] = useState<LivePane>("sessions");
  const [refresh, setRefresh] = useState(0);
  const [cursor, setCursor] = useState(0);
  const selectedRef = useRef<AgentRunSummary | null>(null);
  selectedRef.current = selected;
  const pendingFocus = useRef(focusRun ?? null);
  useEffect(() => {
    pendingFocus.current = focusRun ?? null;
  }, [focusRun]);

  useVisiblePolling((isCurrent) => {
    const sourcesRequest = api<Record<string, AgentSourceHealth>>("/api/agents/sources")
      .then((body) => { if (isCurrent()) setSources(body); })
      .catch((e) => { if (isCurrent()) setError(String(e)); });
    const runsRequest = api<AgentRunsPage>("/api/agents/runs?" + new URLSearchParams({ limit: "30", cursor: String(cursor) }))
      .then((body) => {
        if (!isCurrent()) return;
        setPage(body);
        const wanted = pendingFocus.current;
        if (wanted) {
          const match = body.items.find((r) => r.sourceId === wanted.sourceId && r.runId === wanted.runId);
          if (match) {
            pendingFocus.current = null;
            setSelected(match);
            return;
          }
        }
        const current = selectedRef.current;
        if (current) {
          const fresh = body.items.find((r) => r.sourceId === current.sourceId && r.runId === current.runId);
          if (fresh) setSelected(fresh);
        }
      })
      .catch((e) => { if (isCurrent()) setError(String(e)); });
    const unboundRequest = api<{ items: AgentBindingCandidate[] }>("/api/agents/unbound?limit=30")
      .then((body) => { if (isCurrent()) setUnbound(body.items); })
      .catch((e) => { if (isCurrent()) setError(String(e)); });
    return Promise.all([sourcesRequest, runsRequest, unboundRequest]);
  }, [refresh, cursor]);

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
      // Scope pro revizi i vrstvu se čte přímo z aktuálního project/workspace,
      // aby vazba nemohla nikdy tiše zamířit do jiného scope.
      const [nodeBindings, view] = await Promise.all([
        api<{ revision: number }>(
          "/api/agents/bindings?" +
            new URLSearchParams({ project, workspace, nodeId: bindNodeId }),
        ),
        api<View>(
          `/api/view?project=${encodeURIComponent(project)}&workspace=${encodeURIComponent(workspace)}`,
        ),
      ]);
      const node = view.graph.nodes.find((n) => n.id === bindNodeId);
      if (!node) throw new Error("Uzel v tomto pracovním prostoru neexistuje.");
      await api("/api/agents/bindings", {
        project,
        workspace,
        layer: node.parentId ?? "",
        nodeId: bindNodeId,
        sourceId: bindTarget.sourceId,
        runId: bindTarget.runId,
        sessionId: null,
        expectedRevision: nodeBindings.revision,
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
      <div className="environment-toolbar live-toolbar" role="toolbar" aria-label="Nástroje Live Run">
        <strong>Live Run</strong>
        {([["sessions", "Relace"], ["cost", "Náklady"], ["memory", "Paměť"], ["sources", "Zdroje"]] as const).map(([id, label]) =>
          <button key={id} aria-pressed={pane === id} onClick={() => setPane(id)}>{label}</button>)}
        <button onClick={() => setRefresh((value) => value + 1)}>Obnovit zdroje</button>
      </div>
      <h2>Agenti · skutečné zdroje</h2>
      <p className="muted">Globální katalog zdrojů. Příslušnost k {project}/{workspace} vzniká pouze explicitní vazbou k uzlu; samotný výběr projektu běhy nefiltruje.</p>
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
      {pane === "sources" && <section className="live-source-info"><h3>Autoritativní zdroje</h3>
        <p>OporaCC API poskytuje procesní osu, větve a worktrees; Bridge telemetrie se čte přes OporaCC.</p>
        <p>Bez přímého čtení provozních databází. Nedostupné není prázdné ani úspěšné. Obnova probíhá jen při viditelném panelu.</p>
      </section>}
      <div className="agents-columns" hidden={pane === "sources"}>
        <div className="agent-run-list">
          <h3>Běhy ({page.total})</h3>
          <div className="live-page-controls">
            <button disabled={cursor === 0} onClick={() => { setCursor(Math.max(0, cursor - 30)); setSelected(null); }}>Předchozí relace</button>
            <button disabled={page.nextCursor === null} onClick={() => { if (page.nextCursor !== null) { setCursor(page.nextCursor); setSelected(null); } }}>Další relace</button>
          </div>
          <small>Načteno {page.items.length} z {page.total} · od pozice {page.total ? cursor + 1 : 0}</small>
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
              <LiveRunDetail run={detail} pane={pane} />
              {pane === "sessions" && detail.brain && (
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
              {pane === "sessions" && <><h4>Bezpečný náhled akcí (bez interního uvažování)</h4>
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
              </ol></>}
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
