import { useRef, useState } from "react";
import { useDesktopState } from "./state-store";
import { NODE_PHASES } from "./types";
import type { DesktopState, NodePhase } from "./types";
import { emptyNodeWorkflow } from "./types";

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `id-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

const PHASE_LABEL: Record<NodePhase, string> = {
  discover: "Objev",
  define: "Definice",
  build: "Build",
  verify: "Ověření",
  live: "Live",
};

function withNode(state: DesktopState, nodeId: string, fn: (node: ReturnType<typeof emptyNodeWorkflow>) => ReturnType<typeof emptyNodeWorkflow>): DesktopState {
  const current = state.nodes[nodeId] ?? emptyNodeWorkflow();
  return { ...state, nodes: { ...state.nodes, [nodeId]: fn(current) } };
}

export function NodeWorkflowPanel({
  project,
  workspace,
  nodeId,
}: {
  project: string;
  workspace: string;
  nodeId: string;
}) {
  const { state, readOnly, loading, error, reload, mutate } = useDesktopState(project, workspace);
  const [newCriterionText, setNewCriterionText] = useState("");
  const [newStepText, setNewStepText] = useState("");
  const [newStepAssignee, setNewStepAssignee] = useState("");
  // Pending writes are tracked per node scope (not one global flag) so that switching to a
  // different node while a write for the previous one is still in flight leaves the new node's
  // own controls interactive, and a late-arriving response can be matched back to (and can only
  // clear the draft of) the exact scope that started it.
  const scope = `${project}::${workspace}::${nodeId}`;
  const scopeRef = useRef(scope);
  scopeRef.current = scope;
  const [busyScopes, setBusyScopes] = useState<ReadonlySet<string>>(() => new Set());
  const busy = busyScopes.has(scope);

  const node = state.nodes[nodeId] ?? emptyNodeWorkflow();
  const phaseIndex = NODE_PHASES.indexOf(node.phase);
  const nextPhase = NODE_PHASES[phaseIndex + 1];
  const criteriaSatisfied = node.criteria.length > 0 && node.criteria.every((c) => c.checked);

  async function run(requestScope: string, fn: (current: DesktopState) => DesktopState): Promise<boolean> {
    setBusyScopes((prev) => new Set(prev).add(requestScope));
    const ok = await mutate(fn);
    setBusyScopes((prev) => {
      if (!prev.has(requestScope)) return prev;
      const next = new Set(prev);
      next.delete(requestScope);
      return next;
    });
    return ok;
  }

  function toggleCriterion(id: string) {
    if (busy) return;
    return run(scope, (current) =>
      withNode(current, nodeId, (n) => ({
        ...n,
        criteria: n.criteria.map((c) => (c.id === id ? { ...c, checked: !c.checked } : c)),
      })),
    );
  }

  function removeCriterion(id: string) {
    if (busy) return;
    return run(scope, (current) => withNode(current, nodeId, (n) => ({ ...n, criteria: n.criteria.filter((c) => c.id !== id) })));
  }

  function addCriterion() {
    if (busy) return;
    const text = newCriterionText.trim();
    if (!text) return;
    const requestScope = scope;
    run(requestScope, (current) =>
      withNode(current, nodeId, (n) => ({ ...n, criteria: n.criteria.concat([{ id: newId(), text, checked: false }]) })),
    ).then((ok) => {
      if (ok && scopeRef.current === requestScope) setNewCriterionText("");
    });
  }

  function toggleStep(id: string) {
    if (busy) return;
    return run(scope, (current) =>
      withNode(current, nodeId, (n) => ({ ...n, steps: n.steps.map((s) => (s.id === id ? { ...s, done: !s.done } : s)) })),
    );
  }

  function removeStep(id: string) {
    if (busy) return;
    return run(scope, (current) => withNode(current, nodeId, (n) => ({ ...n, steps: n.steps.filter((s) => s.id !== id) })));
  }

  function addStep() {
    if (busy) return;
    const text = newStepText.trim();
    if (!text) return;
    const assignee = newStepAssignee.trim() || "nepřiřazeno";
    const requestScope = scope;
    run(requestScope, (current) =>
      withNode(current, nodeId, (n) => ({ ...n, steps: n.steps.concat([{ id: newId(), text, assignee, done: false }]) })),
    ).then((ok) => {
      if (ok && scopeRef.current === requestScope) {
        setNewStepText("");
        setNewStepAssignee("");
      }
    });
  }

  function advance() {
    if (busy || !nextPhase || !criteriaSatisfied) return;
    run(scope, (current) => withNode(current, nodeId, (n) => ({ ...n, phase: nextPhase })));
  }

  function goToEarlierPhase(phase: NodePhase) {
    if (busy) return;
    const targetIndex = NODE_PHASES.indexOf(phase);
    if (targetIndex >= phaseIndex) return;
    run(scope, (current) => withNode(current, nodeId, (n) => ({ ...n, phase })));
  }

  const stepsDone = node.steps.filter((s) => s.done).length;

  return (
    <section className="v3-panel v3-node-workflow" aria-label="Životní cyklus uzlu">
      <header className="v3-panel-head">
        <h2>Uzel {nodeId}</h2>
        {readOnly && <p role="status" className="v3-readonly">Main je pouze pro čtení; změny se neuloží.</p>}
      </header>
      {loading && <p role="status">Načítám stav uzlu…</p>}
      {error && (
        <p role="alert" className="v3-error">
          {error}{" "}
          <button type="button" onClick={reload}>
            Znovu načíst
          </button>
        </p>
      )}
      {!loading && (
        <>
          <div className="v3-life" role="tablist" aria-label="Fáze uzlu">
            {NODE_PHASES.map((phase, index) => (
              <button
                key={phase}
                type="button"
                role="tab"
                aria-selected={phase === node.phase}
                className={`v3-phase${index < phaseIndex ? " v3-phase-done" : phase === node.phase ? " v3-phase-cur" : ""}`}
                disabled={readOnly || busy || index >= phaseIndex}
                onClick={() => goToEarlierPhase(phase)}
              >
                {PHASE_LABEL[phase]}
              </button>
            ))}
          </div>
          <p className="v3-note">
            Fáze je plánovací stav člověka, ne automatický důkaz testů či nasazení. Postup vpřed vyžaduje neprázdná
            splněná kritéria; návrat je možný kdykoli.
          </p>

          <section className="v3-section" aria-label="Kritéria postupu">
            <h3>Kritéria fáze {PHASE_LABEL[node.phase]}</h3>
            {node.criteria.length === 0 && <p className="v3-empty">Zatím žádná kritéria.</p>}
            <ul className="v3-criteria-list">
              {node.criteria.map((criterion) => (
                <li key={criterion.id} className="v3-criterion">
                  <label>
                    <input
                      type="checkbox"
                      checked={criterion.checked}
                      disabled={readOnly || busy}
                      onChange={() => toggleCriterion(criterion.id)}
                    />
                    {criterion.text}
                  </label>
                  <button type="button" disabled={readOnly || busy} onClick={() => removeCriterion(criterion.id)}>
                    Odebrat
                  </button>
                </li>
              ))}
            </ul>
            <div className="v3-row">
              <input
                aria-label="Nové kritérium"
                value={newCriterionText}
                disabled={readOnly || busy}
                onChange={(e) => setNewCriterionText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") addCriterion();
                }}
              />
              <button type="button" disabled={readOnly || busy || !newCriterionText.trim()} onClick={addCriterion}>
                Přidat kritérium
              </button>
            </div>
            <div className="v3-row">
              <button type="button" disabled={readOnly || busy || !nextPhase || !criteriaSatisfied} onClick={advance}>
                {nextPhase ? `Postoupit → ${PHASE_LABEL[nextPhase]}` : "Poslední fáze"}
              </button>
            </div>
          </section>

          <section className="v3-section" aria-label="Kroky sestavení">
            <h3>
              Kroky {stepsDone} / {node.steps.length} hotovo
            </h3>
            {node.steps.length === 0 && <p className="v3-empty">Zatím žádné kroky.</p>}
            <ul className="v3-step-list">
              {node.steps.map((step, index) => (
                <li key={step.id} className={`v3-step${step.done ? " v3-step-done" : ""}`}>
                  <input
                    type="checkbox"
                    aria-label={`Krok ${index + 1} hotovo`}
                    checked={step.done}
                    disabled={readOnly || busy}
                    onChange={() => toggleStep(step.id)}
                  />
                  <span className="v3-step-n">#{index + 1}</span>
                  <span className="v3-step-text">{step.text}</span>
                  <span className="v3-chip">{step.assignee}</span>
                  <button type="button" disabled={readOnly || busy} onClick={() => removeStep(step.id)}>
                    Odebrat
                  </button>
                </li>
              ))}
            </ul>
            <div className="v3-row">
              <input
                aria-label="Nový krok"
                value={newStepText}
                disabled={readOnly || busy}
                onChange={(e) => setNewStepText(e.target.value)}
              />
              <input
                aria-label="Přiřazení kroku"
                placeholder="nepřiřazeno"
                value={newStepAssignee}
                disabled={readOnly || busy}
                onChange={(e) => setNewStepAssignee(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") addStep();
                }}
              />
              <button type="button" disabled={readOnly || busy || !newStepText.trim()} onClick={addStep}>
                Přidat krok
              </button>
            </div>
          </section>
        </>
      )}
    </section>
  );
}
