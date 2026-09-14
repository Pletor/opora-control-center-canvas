import { useState } from "react";
import { HUMAN, STATE_LABEL, STEP_LABEL, markStep, transitionProcess, type Allowed, type Process, type ProcessState, type Report } from "@/editor/node-detail/process/logic/processes";

/** Jeden proces: stav, kroky s důkazy, přechody podle tabulky a poslední odpovědi agentů. */
export default function ProcessCard({ project, process, allowed, reports, onChange, onError }: {
  project: string;
  process: Process;
  allowed: Allowed;
  reports: Report[];
  onChange: (process: Process) => void;
  onError: (message: string) => void;
}) {
  const [fix, setFix] = useState(process.failure?.fix ?? "");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [evidence, setEvidence] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<Process>) {
    setBusy(true);
    try {
      onChange(await action());
    } catch (exc) {
      onError((exc as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function transitionButton(to: ProcessState) {
    const label = { draft: "Zpět do návrhu", running: process.state === "repair" ? "Opraveno, pokračovat" : "Spustit proces", done: "Označit hotovo", repair: "Poslat do oprav" }[to];
    return (
      <button
        key={to}
        type="button"
        className={to === "done" ? "primary" : to === "repair" ? "danger" : ""}
        disabled={busy}
        onClick={() => {
          if (to === "repair") {
            if (!reason.trim()) return onError("Napište, co je rozbité.");
            return run(() => transitionProcess(project, process, "repair", note, { failure: { reason: reason.trim(), stepId: null, reportedBy: HUMAN } }));
          }
          if (to === "running" && process.state === "repair") {
            return run(() => transitionProcess(project, process, "running", note, { fix: fix.trim() }));
          }
          return run(() => transitionProcess(project, process, to, note));
        }}
      >
        {label}
      </button>
    );
  }

  return (
    <article className={"process process-" + process.state} aria-label={process.title}>
      <header className="process-head">
        <span className={"process-state state-" + process.state}>{STATE_LABEL[process.state]}</span>
        <strong>{process.title}</strong>
        <span className="muted">rev. {process.revision} · {process.owner.name}</span>
      </header>

      {process.failure && (
        <div className="process-failure">
          <strong>Porucha:</strong> {process.failure.reason}
          {process.failure.fix && <div><strong>Oprava:</strong> {process.failure.fix}</div>}
        </div>
      )}

      <ol className="process-steps">
        {process.steps.map((step) => (
          <li key={step.id} className={"step step-" + step.state}>
            <div className="step-row">
              <span className="step-state">{STEP_LABEL[step.state]}</span>
              <span className="step-title">{step.title}</span>
              {process.state === "running" && step.state !== "done" && (
                <span className="step-actions">
                  <input
                    aria-label={"Důkaz kroku " + step.title}
                    placeholder="důkaz (co bylo ověřeno)"
                    value={evidence[step.id] ?? ""}
                    onChange={(e) => setEvidence({ ...evidence, [step.id]: e.target.value })}
                  />
                  <button type="button" disabled={busy || !(evidence[step.id] ?? "").trim()} onClick={() => run(() => markStep(project, process, step.id, "done", evidence[step.id]))}>Hotovo</button>
                </span>
              )}
            </div>
            {step.evidence && <p className="step-evidence">{step.evidence.summary} <span className="muted">· {step.evidence.by.name}</span></p>}
          </li>
        ))}
        {process.steps.length === 0 && <li className="muted">Proces zatím nemá kroky.</li>}
      </ol>

      <div className="process-controls">
        {process.state === "draft" && !process.inputs.worktree && (
          <p className="muted">Bez přiřazeného worktree; do poznámky napište „bez worktree“, pokud proces kód nemění.</p>
        )}
        {process.state === "repair" && (
          <label className="field">Popis opravy<input value={fix} onChange={(e) => setFix(e.target.value)} placeholder="co se opravilo" /></label>
        )}
        {(process.state === "running" || process.state === "done") && (
          <label className="field">Co je rozbité (pro přechod do oprav)<input value={reason} onChange={(e) => setReason(e.target.value)} /></label>
        )}
        <label className="field">Poznámka k přechodu<input value={note} onChange={(e) => setNote(e.target.value)} /></label>
        <div className="process-actions">{allowed.human.map(transitionButton)}</div>
      </div>

      {reports.length > 0 && (
        <details className="process-reports">
          <summary>Odpovědi agentů ({reports.length})</summary>
          <ul>
            {reports.slice(-10).reverse().map((report) => (
              <li key={report.id} className={"report report-" + report.kind}>
                <span className="muted">{report.at} · {report.by.name} · {report.kind}{report.stale ? " · zastaralá revize" : ""}</span>
                <div>{report.summary}</div>
                {report.error && <div className="report-error">{report.error}</div>}
              </li>
            ))}
          </ul>
        </details>
      )}

      <details className="process-history">
        <summary>Historie ({process.history.length})</summary>
        <ul>
          {process.history.map((entry, index) => (
            <li key={index}><span className="muted">{entry.at}</span> {entry.from ? STATE_LABEL[entry.from] + " → " : ""}{STATE_LABEL[entry.to]} · {entry.by.name}{entry.note ? " · " + entry.note : ""}</li>
          ))}
        </ul>
      </details>
      <code className="identity">{process.id}</code>
    </article>
  );
}
