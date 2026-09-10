import { useEffect, useRef, useState } from "react";
import { errorMessage, fetchHandoffRuns, fetchPlanningRuns } from "./api";
import { useDesktopState } from "./state-store";
import type { HandoffRun, PlanningRun, Ticket, TicketPriority, TicketStatus } from "./types";

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `id-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

const HANDOFF_STATUS_LABEL: Record<string, string> = {
  prepared: "Připraveno — model neběží",
  starting: "Spouští se",
  running: "Běží",
  stopping: "Zastavuje se",
  verifying: "Ověřuje se výsledek",
  completed: "Dokončeno",
  failed: "Selhalo",
  cancelled: "Zastaveno",
  interrupted: "Přerušeno",
};

function matches(query: string, ...fields: (string | null | undefined)[]): boolean {
  if (!query) return true;
  const q = query.toLowerCase();
  return fields.some((f) => (f || "").toLowerCase().includes(q));
}

export function LiveWorkspacePanel({
  project,
  workspace,
  nodeId,
}: {
  project: string;
  workspace: string;
  nodeId?: string;
}) {
  const [planningRuns, setPlanningRuns] = useState<PlanningRun[]>([]);
  const [handoffRuns, setHandoffRuns] = useState<HandoffRun[]>([]);
  const [search, setSearch] = useState("");
  const [planningLoading, setPlanningLoading] = useState(true);
  const [handoffLoading, setHandoffLoading] = useState(true);
  const [planningError, setPlanningError] = useState("");
  const [handoffError, setHandoffError] = useState("");
  const generation = useRef(0);
  const scopeKey = useRef("");
  const { state, readOnly, mutate } = useDesktopState(project, workspace);
  const [newTicketTitle, setNewTicketTitle] = useState("");
  const [newTicketPriority, setNewTicketPriority] = useState<TicketPriority>("normal");
  const [newTicketSessionId, setNewTicketSessionId] = useState("");
  const [ticketBusy, setTicketBusy] = useState(false);
  const [ticketError, setTicketError] = useState("");

  // Planning and handoff runs are fetched independently: an outage of one source must not hide
  // data that the other source already returned (Promise.all would reject/lose both on a single
  // failure). Both are still gated by the same scope ticket so a project/workspace switch drops
  // in-flight responses that belong to the scope left behind.
  const load = () => {
    const ticket = ++generation.current;
    const scope = `${project}::${workspace}`;
    scopeKey.current = scope;
    setPlanningLoading(true);
    setHandoffLoading(true);
    setPlanningError("");
    setHandoffError("");
    fetchPlanningRuns(project)
      .then((planning) => {
        if (ticket !== generation.current || scopeKey.current !== scope) return;
        setPlanningRuns(planning.runs.filter((r) => r.workspace === workspace));
        setPlanningLoading(false);
      })
      .catch((e) => {
        if (ticket !== generation.current || scopeKey.current !== scope) return;
        setPlanningError(errorMessage(e));
        setPlanningLoading(false);
      });
    fetchHandoffRuns(project, workspace)
      .then((handoff) => {
        if (ticket !== generation.current || scopeKey.current !== scope) return;
        setHandoffRuns(handoff.runs);
        setHandoffLoading(false);
      })
      .catch((e) => {
        if (ticket !== generation.current || scopeKey.current !== scope) return;
        setHandoffError(errorMessage(e));
        setHandoffLoading(false);
      });
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project, workspace]);

  const visiblePlanning = planningRuns
    .filter((r) => !nodeId || r.layer === nodeId)
    .filter((r) => matches(search, r.id, r.status, r.message, r.output, r.layer));
  const visibleHandoff = handoffRuns
    .filter((r) => !nodeId || r.scope.node === nodeId)
    .filter((r) => matches(search, r.id, r.status, r.task, r.error));
  const tickets = Object.values(state.tickets ?? [])
    .filter((t) => !nodeId || t.nodeId === nodeId)
    .filter((t) => matches(search, t.title, t.status, t.priority));

  function setTicketStatus(id: string, status: TicketStatus) {
    mutate((current) => ({
      ...current,
      tickets: current.tickets.map((t) => (t.id === id ? { ...t, status } : t)),
    }));
  }

  async function createTicket() {
    const title = newTicketTitle.trim();
    if (!title) return;
    setTicketBusy(true);
    setTicketError("");
    const ticket: Ticket = {
      id: newId(),
      title,
      priority: newTicketPriority,
      status: "open",
      nodeId: nodeId || "",
      sessionId: newTicketSessionId.trim(),
      // Created through this explicit human form action; never attribute ticket authorship to
      // an agent identity that was not actually confirmed by a person.
      createdBy: "human",
    };
    const ok = await mutate((current) => ({ ...current, tickets: current.tickets.concat([ticket]) }));
    setTicketBusy(false);
    if (ok) {
      setNewTicketTitle("");
      setNewTicketPriority("normal");
      setNewTicketSessionId("");
    } else {
      setTicketError("Ticket se nepodařilo uložit.");
    }
  }

  // Real, timestamped events only: handoff run events and pinned/authored decisions. No
  // fabricated percentages or synthetic zeros — context-window/compaction telemetry is simply
  // not available through this API and must say so explicitly.
  type TimelineEntry = { at: string; label: string; by: string };
  const timeline: TimelineEntry[] = [
    ...state.decisions
      .filter((d) => !nodeId || d.nodeId === nodeId)
      .map((d) => ({ at: d.createdAt, label: `Rozhodnutí: ${d.text}`, by: d.by === "agent" ? "agent" : "člověk" })),
    ...visibleHandoff.flatMap((run) =>
      (run.events || []).map((e) => ({
        at: e.observedAt || "",
        label: `Handoff ${run.id}: ${e.kind}`,
        by: "systém",
      })),
    ),
    ...visiblePlanning.map((run) => ({
      at: run.updated_at,
      label: `Návrhový běh ${run.id}: ${run.status}`,
      by: "systém",
    })),
  ]
    .filter((e) => e.at)
    .sort((a, b) => (a.at < b.at ? 1 : a.at > b.at ? -1 : 0));

  return (
    <section className="v3-panel v3-live-workspace" aria-label="Live workspace">
      <header className="v3-panel-head">
        <h2>Live run</h2>
        <div className="v3-row">
          <input
            aria-label="Hledat v bězích a ticketech"
            placeholder="Hledat…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button type="button" disabled={planningLoading || handoffLoading} onClick={load}>
            Obnovit (jen čtení)
          </button>
        </div>
      </header>
      <section className="v3-section" aria-label="Návrhové běhy">
        <h3>Návrhové běhy · {visiblePlanning.length}</h3>
        {planningLoading && <p role="status">Načítám návrhové běhy…</p>}
        {planningError && (
          <p role="alert" className="v3-error">
            {planningError}{" "}
            <button type="button" onClick={load}>
              Zkusit znovu
            </button>
          </p>
        )}
        {!planningLoading && !planningError && (
          <>
            {visiblePlanning.length === 0 && <p className="v3-empty">Žádný návrhový běh neodpovídá filtru.</p>}
            <ul className="v3-run-list">
              {visiblePlanning.map((run) => (
                <li key={run.id} className="v3-run">
                  <div className="v3-row">
                    <code>{run.id}</code>
                    <span className="v3-chip">{run.layer || "bez uzlu"}</span>
                    <span className={`v3-chip${run.status === "completed" && run.output ? " v3-chip-ok" : ""}`}>
                      {run.status === "completed" && run.output ? "Návrh dokončen" : run.status}
                    </span>
                  </div>
                  <p>{run.message}</p>
                  {run.output && (
                    <details>
                      <summary>Výstup návrhu</summary>
                      <pre data-testid={`planning-output-${run.id}`}>{run.output}</pre>
                    </details>
                  )}
                  <p className="v3-note">
                    Náklady: {run.provider_billing != null ? `${run.provider_billing} USD` : "nedostupné"} · aktualizováno{" "}
                    {run.updated_at}
                  </p>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section className="v3-section" aria-label="Handoff běhy">
        <h3>Handoff běhy · {visibleHandoff.length}</h3>
        {handoffLoading && <p role="status">Načítám handoff běhy…</p>}
        {handoffError && (
          <p role="alert" className="v3-error">
            {handoffError}{" "}
            <button type="button" onClick={load}>
              Zkusit znovu
            </button>
          </p>
        )}
        {!handoffLoading && !handoffError && (
          <>
            {visibleHandoff.length === 0 && <p className="v3-empty">Žádný handoff běh neodpovídá filtru.</p>}
            <ul className="v3-run-list">
              {visibleHandoff.map((run) => (
                <li key={run.id} className="v3-run">
                  <div className="v3-row">
                    <code>{run.id}</code>
                    <span className="v3-chip">{run.scope.node || "bez uzlu"}</span>
                    <span className="v3-chip">{HANDOFF_STATUS_LABEL[run.status] || run.status}</span>
                  </div>
                  <p>{run.task}</p>
                  {!!run.events?.length && (
                    <details>
                      <summary>Události</summary>
                      <ol>
                        {run.events.map((e, i) => (
                          <li key={i}>
                            {e.observedAt} {e.kind}
                          </li>
                        ))}
                      </ol>
                    </details>
                  )}
                  {run.result && (
                    <details>
                      <summary>Výsledek</summary>
                      <pre data-testid={`handoff-result-${run.id}`}>{run.result.content}</pre>
                    </details>
                  )}
                  {run.error && <p role="alert">{run.error}</p>}
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section className="v3-section" aria-label="Tickety">
        <h3>Tickety · {tickets.length}</h3>
        {readOnly && <p role="status" className="v3-readonly">Main je pouze pro čtení; ticket nelze založit ani měnit.</p>}
        {ticketError && <p role="alert" className="v3-error">{ticketError}</p>}
        <div className="v3-row">
          <input
            aria-label="Název nového ticketu"
            placeholder="Název ticketu"
            value={newTicketTitle}
            disabled={readOnly || ticketBusy}
            onChange={(e) => setNewTicketTitle(e.target.value)}
          />
          <select
            aria-label="Priorita nového ticketu"
            value={newTicketPriority}
            disabled={readOnly || ticketBusy}
            onChange={(e) => setNewTicketPriority(e.target.value as TicketPriority)}
          >
            <option value="low">nízká</option>
            <option value="normal">normální</option>
            <option value="high">vysoká</option>
          </select>
          <input
            aria-label="Session ID nového ticketu"
            placeholder="session (volitelné)"
            value={newTicketSessionId}
            disabled={readOnly || ticketBusy}
            onChange={(e) => setNewTicketSessionId(e.target.value)}
          />
          <button type="button" disabled={readOnly || ticketBusy || !newTicketTitle.trim()} onClick={createTicket}>
            Založit ticket
          </button>
        </div>
        <p className="v3-note">Vázáno na uzel {nodeId || "bez uzlu"} · autor: člověk.</p>
        {tickets.length === 0 && <p className="v3-empty">Žádný ticket neodpovídá filtru.</p>}
        <ul className="v3-ticket-list">
          {tickets.map((ticket) => (
            <li key={ticket.id} className="v3-ticket">
              <span className="v3-ticket-title">{ticket.title}</span>
              <span className="v3-chip">{ticket.priority}</span>
              <span className="v3-chip">{ticket.createdBy === "agent" ? "agent" : "člověk"}</span>
              {ticket.sessionId && <span className="v3-chip">{ticket.sessionId}</span>}
              <select
                aria-label={`Stav ticketu ${ticket.title}`}
                value={ticket.status}
                disabled={readOnly}
                onChange={(e) => setTicketStatus(ticket.id, e.target.value as TicketStatus)}
              >
                <option value="open">otevřeno</option>
                <option value="doing">probíhá</option>
                <option value="done">hotovo</option>
              </select>
            </li>
          ))}
        </ul>
      </section>

      <section className="v3-section" aria-label="Kontext a osa">
        <h3>Kontext a osa</h3>
        <p className="v3-note">
          Kontextové okno: nedostupné · Průběh kompaktace: nedostupné — toto API tuto telemetrii neposkytuje;
          zobrazovat vymyšlená čísla by bylo zavádějící.
        </p>
        {timeline.length === 0 && <p className="v3-empty">Zatím žádné skutečné události v ose.</p>}
        <ul className="v3-run-list">
          {timeline.map((entry, i) => (
            <li key={i} className="v3-run">
              <div className="v3-row">
                <code>{entry.at}</code>
                <span className="v3-chip">{entry.by}</span>
              </div>
              <p>{entry.label}</p>
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
}
