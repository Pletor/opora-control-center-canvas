/** Kontextová akce „úkol pro agenta“: připraví typovaný scope, nespouští žádný běh. */
export type AgentTaskRequest = {
  project: string;
  workspace: string;
  /** Vrstva plátna, ve které člověk pracuje; null je kořen projektu. */
  layer: string | null;
  nodeId: string;
  nodeName: string;
  source: "block" | "journal" | "canvas";
  text: string;
  requestedAt: string;
};

export const AGENT_TASK_EVENT = "opora:agent-task-request";

/** Placeholder pro panel agenta, který doplní rodičovská integrace. */
declare global {
  interface Window {
    oporaAgentTaskHook?: (request: AgentTaskRequest) => void;
  }
}

export function emitAgentTask(request: AgentTaskRequest): AgentTaskRequest {
  window.oporaAgentTaskHook?.(request);
  window.dispatchEvent(new CustomEvent<AgentTaskRequest>(AGENT_TASK_EVENT, { detail: request }));
  return request;
}

/** Potvrzení pro člověka: co přesně by panel agenta dostal. Žádný placený běh zde nevzniká. */
export function AgentTaskNotice({
  request,
  onDismiss,
}: {
  request: AgentTaskRequest;
  onDismiss: () => void;
}) {
  return (
    <div className="agent-task-notice" role="status" data-testid="agent-task-notice">
      <strong>Úkol připraven k předání</strong>
      <dl>
        <div>
          <dt>Projekt</dt>
          <dd>{request.project}</dd>
        </div>
        <div>
          <dt>Prostor</dt>
          <dd>{request.workspace}</dd>
        </div>
        <div>
          <dt>Vrstva</dt>
          <dd data-testid="agent-task-layer">{request.layer ?? "kořen projektu"}</dd>
        </div>
        <div>
          <dt>Uzel</dt>
          <dd data-testid="agent-task-node">
            {request.nodeName} ({request.nodeId})
          </dd>
        </div>
        <div>
          <dt>Zadání</dt>
          <dd data-testid="agent-task-text">{request.text || "(prázdný blok)"}</dd>
        </div>
      </dl>
      <p className="muted">
        Panel agenta připojí rodičovská integrace. Zde nevzniká placený běh ani session.
      </p>
      <button type="button" onClick={onDismiss}>
        Zavřít
      </button>
    </div>
  );
}
