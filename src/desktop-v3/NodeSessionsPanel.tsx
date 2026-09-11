import { useEffect, useMemo, useRef, useState } from "react";
import { fetchNodeSessions, errorMessage, type NodeSession, type SessionEvent } from "./node-sessions";
import "./node-sessions.css";

const STATUS_LABEL: Record<NodeSession["status"], string> = {
  running: "Běží",
  recent_activity: "Nedávná aktivita",
  idle: "Nečinné",
  completed: "Dokončeno",
  failed: "Selhalo",
  unknown: "Neznámý stav",
};
const ROLE_LABEL: Record<NodeSession["role"], string> = { orchestrator: "Orchestrátor", worker: "Pracovní" };
const POLL_MS = 3500;
const TIMEOUT_MS = 8000;

function fmtTime(value: string | null): string {
  if (!value) return "nedostupné";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString("cs-CZ");
}
function fmtNum(value: number | null): string {
  return value === null || value === undefined ? "nedostupné" : String(value);
}
function fmtCost(value: number | null): string {
  return value === null || value === undefined ? "nedostupné" : `${value.toFixed(4)} USD`;
}
function sortByActivity(a: NodeSession, b: NodeSession): number {
  return (b.lastActivityAt || b.boundAt || "").localeCompare(a.lastActivityAt || a.boundAt || "");
}
function sortEvents(a: SessionEvent, b: SessionEvent): number {
  return (b.at || "").localeCompare(a.at || "");
}

/** Samostatná plocha viditelnosti sessions vázaných na uzel (Hermes/Telegram i Claude CLI).
 * Jen čtení a bezpečná metadata — žádné ovládání, žádné vymyšlené stavy ani obsah zpráv. */
export function NodeSessionsPanel({ project, workspace, nodeId }: { project: string; workspace: string; nodeId?: string }) {
  const [sessions, setSessions] = useState<NodeSession[]>([]);
  const [truncated, setTruncated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [allNodes, setAllNodes] = useState(false);
  const [selectedId, setSelectedId] = useState("");
  const [refresh, setRefresh] = useState(0);
  const version = useRef(0);
  const cardRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  const effectiveNodeId = nodeId && !allNodes ? nodeId : undefined;

  useEffect(() => {
    setSessions([]);
    setError("");
    setSelectedId("");
    setLoading(true);
    version.current++;
  }, [project, workspace, effectiveNodeId]);

  useEffect(() => {
    let alive = true;
    const timers = new Set<ReturnType<typeof setTimeout>>();
    const controllers = new Set<AbortController>();
    const schedule = () => {
      const timer = setTimeout(() => {
        timers.delete(timer);
        void load();
      }, POLL_MS);
      timers.add(timer);
    };
    const load = async () => {
      if (!alive) return;
      if (document.hidden) {
        schedule();
        return;
      }
      const myVersion = version.current;
      const controller = new AbortController();
      controllers.add(controller);
      const deadline = setTimeout(() => controller.abort(), TIMEOUT_MS);
      try {
        const body = await fetchNodeSessions(project, workspace, effectiveNodeId, controller.signal);
        if (!alive || myVersion !== version.current) return;
        if (body.project !== project || body.workspace !== workspace) throw new Error("Odpověď neodpovídá zvolenému rozsahu.");
        setSessions(body.sessions);
        setTruncated(body.truncated);
        setError("");
      } catch (e) {
        if (alive && myVersion === version.current) {
          setError(controller.signal.aborted ? "Zdroj neodpověděl do 8 s." : errorMessage(e));
        }
      } finally {
        clearTimeout(deadline);
        controllers.delete(controller);
        if (alive) {
          setLoading(false);
          schedule();
        }
      }
    };
    void load();
    return () => {
      alive = false;
      timers.forEach(clearTimeout);
      controllers.forEach((c) => c.abort());
    };
  }, [project, workspace, effectiveNodeId, refresh]);

  const displaySessions = useMemo(() => error ? sessions.map((s): NodeSession => s.closedAt ? s : ({
    ...s, status: "unknown", sourceAvailable: false,
    statusReason: "Spojení přerušeno; poslední uložený stav nelze považovat za živý.",
  })) : sessions, [sessions, error]);
  const orchestrators = useMemo(() => displaySessions.filter((s) => s.role === "orchestrator").sort(sortByActivity), [displaySessions]);
  const workers = useMemo(() => displaySessions.filter((s) => s.role === "worker").sort(sortByActivity), [displaySessions]);
  const ordered = useMemo(() => [...orchestrators, ...workers], [orchestrators, workers]);
  const selected = ordered.find((s) => s.id === selectedId) || (!selectedId ? ordered[0] : undefined);
  const parentTitle = selected?.parentSessionId ? sessions.find((s) => s.sessionId === selected.parentSessionId)?.title : undefined;

  const hermesSessions = displaySessions.filter((s) => s.source === "hermes");
  const claudeSessions = displaySessions.filter((s) => s.source === "claude");
  const sourceSummary = (label: string, rows: NodeSession[]) => {
    if (!rows.length) return { label, state: "none" as const, text: "žádné vázané sessions" };
    const unavailable = rows.filter((r) => !r.sourceAvailable);
    if (unavailable.length) return { label, state: "error" as const, text: unavailable[0].statusReason || "zdroj nedostupný" };
    return { label, state: "ok" as const, text: `${rows.length} vázáno` };
  };
  const summaries = [sourceSummary("Hermes · Telegram", hermesSessions), sourceSummary("Claude · CLI", claudeSessions)];

  const headerNodeName = !allNodes && nodeId ? sessions.find((s) => s.nodeId === nodeId)?.nodeName : undefined;

  function onListKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    if (!ordered.length) return;
    const currentIndex = ordered.findIndex((s) => s.id === selected?.id);
    let nextIndex = -1;
    if (e.key === "ArrowDown") nextIndex = Math.min(ordered.length - 1, currentIndex + 1);
    else if (e.key === "ArrowUp") nextIndex = Math.max(0, currentIndex - 1);
    else if (e.key === "Home") nextIndex = 0;
    else if (e.key === "End") nextIndex = ordered.length - 1;
    else return;
    e.preventDefault();
    const next = ordered[nextIndex];
    if (next) {
      setSelectedId(next.id);
      cardRefs.current[next.id]?.focus();
    }
  }

  const renderCard = (s: NodeSession) => (
    <button
      key={s.id}
      ref={(el) => {
        cardRefs.current[s.id] = el;
      }}
      className="ns-card"
      aria-pressed={s.id === selected?.id}
      onClick={() => setSelectedId(s.id)}
    >
      <span className="ns-card-top">
        <span>{s.sourceLabel}</span>
        <span className={`ns-status ns-status-${s.status}`}>{STATUS_LABEL[s.status]}</span>
      </span>
      <strong>{s.title}</strong>
      {s.closedAt && <span className="ns-note">Sledování úkolu uzavřeno</span>}
      <code>{s.sessionId}</code>
      <span className="ns-card-meta">{!s.sourceAvailable && <span className="ns-card-warn">Zdroj nedostupný · </span>}{fmtTime(s.lastActivityAt)}{s.model ? ` · ${s.model}` : ""}</span>
    </button>
  );

  return (
    <section className="node-sessions" aria-label="Práce na uzlu — živé sessions">
      <header className="ns-header">
        <div className="ns-scope">
          <span className="ns-eyebrow">Práce na uzlu · živé sledování</span>
          <h2>{headerNodeName || (effectiveNodeId ? effectiveNodeId : "Všechny uzly prostředí")}</h2>
          <p className="ns-note">
            {workspace} · {effectiveNodeId ? "Sessions vázané na tento uzel." : "Sessions napříč celým prostředím."}
          </p>
        </div>
        {nodeId && (
          <label className="ns-check">
            <input type="checkbox" checked={allNodes} onChange={(e) => setAllNodes(e.target.checked)} />
            Zobrazit všechny uzly prostředí
          </label>
        )}
        <div className="ns-source-health" aria-label="Dostupnost zdrojů">
          {summaries.map((s) => (
            <span key={s.label} className={s.state === "error" ? "is-error" : s.state === "none" ? "is-none" : ""}>
              {s.label} · {s.text}
            </span>
          ))}
        </div>
        <button onClick={() => setRefresh((x) => x + 1)} disabled={loading}>
          Obnovit (jen čtení)
        </button>
      </header>
      {error && (
        <p className="ns-source-error" role="alert">
          {error}. Zobrazené sessions mohou být neaktuální.
        </p>
      )}
      {truncated && <p className="ns-note ns-truncated">Zdroj vrátil více sessions než limit (100); seznam je oříznutý.</p>}
      <div className="ns-columns">
        <aside className="ns-shelf" aria-label="Vázané sessions" onKeyDown={onListKeyDown}>
          {loading && !sessions.length && <p role="status" className="ns-note">Načítám vázané sessions…</p>}
          <div className="ns-group">
            <h3>Orchestrátor <span>{orchestrators.length}</span></h3>
            {orchestrators.length ? <div className="ns-card-list">{orchestrators.map(renderCard)}</div> : <p className="ns-empty">Žádná orchestrátor session.</p>}
          </div>
          <div className="ns-group">
            <h3>Pracovní sessions <span>{workers.length}</span></h3>
            {workers.length ? <div className="ns-card-list">{workers.map(renderCard)}</div> : <p className="ns-empty">Žádná pracovní session.</p>}
          </div>
          {!loading && !sessions.length && !error && <p className="ns-empty">Pro tento rozsah zatím nejsou vázané žádné sessions.</p>}
        </aside>
        <section className="ns-timeline-pane" aria-label="Aktivita vybrané session">
          <header className="ns-pane-head">
            <span className="ns-eyebrow">Aktivita</span>
            <h3>{selected ? selected.title : "Vyberte session"}</h3>
          </header>
          {selected ? (
            <>
              <p className="ns-note">Poslední aktivita zdroje: {fmtTime(selected.lastActivityAt)}</p>
              {selected.events.length ? (
                <ol className="ns-timeline">
                  {[...selected.events].sort(sortEvents).map((e) => (
                    <li key={e.id}>
                      <time>{fmtTime(e.at)}</time>
                      <strong>{e.kind}</strong>
                      <span>{e.summary}</span>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="ns-empty">Zdroj zatím nehlásí žádné bezpečné události.</p>
              )}
            </>
          ) : (
            <p className="ns-empty">Vyberte session vlevo. Pokud žádná není, zatím nebyla přiřazena.</p>
          )}
        </section>
        <aside className="ns-details" aria-label="Detail a ovládání">
          {selected ? (
            <>
              <header className="ns-pane-head">
                <span className="ns-eyebrow">{ROLE_LABEL[selected.role]} · {selected.sourceLabel}</span>
                <span className={`ns-status ns-status-${selected.status}`}>{STATUS_LABEL[selected.status]}</span>
              </header>
              <p className="ns-note">{selected.statusReason}</p>
              <dl className="ns-kv">
                <dt>Session ID</dt><dd><code>{selected.sessionId}</code></dd>
                <dt>Nadřazená session</dt><dd>{selected.parentSessionId ? <>{parentTitle ? `${parentTitle} · ` : ""}<code>{selected.parentSessionId}</code></> : "žádná (kořen)"}</dd>
                <dt>Uzel</dt><dd>{selected.nodeName || selected.nodeId}</dd>
                <dt>Model</dt><dd>{selected.model || "nedostupné"}</dd>
                <dt>Svázáno</dt><dd>{fmtTime(selected.boundAt)}</dd>
                {selected.closedAt && <><dt>Sledování ukončeno</dt><dd>{fmtTime(selected.closedAt)}</dd></>}
                <dt>Zdroj při posledním čtení</dt><dd>{selected.sourceAvailable ? "Dostupný" : "Nedostupný"}</dd>
              </dl>
              <div className="ns-metrics">
                <div><strong>{fmtNum(selected.metrics.inputTokens)}</strong><span>Vstupní tokeny</span></div>
                <div><strong>{fmtNum(selected.metrics.outputTokens)}</strong><span>Výstupní tokeny</span></div>
                <div><strong>{fmtCost(selected.metrics.costUsd)}</strong><span>Náklady hlášené zdrojem</span></div>
              </div>
              {selected.source === "hermes" && <p className="ns-note">Metriky Hermes jsou za celou session, nikoli jen za tento uzel.</p>}
              {selected.role === "worker" && selected.status === "completed" && (
                <p className="ns-note">Dokončení znamená konec tahu modelu, ne ověřené dokončení úkolu na uzlu.</p>
              )}
              <div className="ns-notice">
                <strong>Ovládání přes původní Telegram/CLI; tento panel pouze sleduje.</strong>
                <p>Žádné tlačítko zde session nespustí, nezastaví ani neobnoví.</p>
              </div>
            </>
          ) : (
            <p className="ns-empty">Detail se zobrazí po výběru session.</p>
          )}
        </aside>
      </div>
    </section>
  );
}
