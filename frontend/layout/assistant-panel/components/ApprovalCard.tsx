import { useState } from "react";
import { cleanNote, NOTE_LIMIT, statusWord, summaryLines, targetScope, targetTitle, type Approval } from "../logic/approval";

export type ApprovalDecision = (approvalId: string, decision: "allow" | "deny", note?: string) => void;

/**
 * Žádost asistenta o zápis na plátno. Nahoře, kam zápis jde (cíl a karta, pod tím projekt, workspace
 * a přesná cesta), pod tím shrnutí payloadu po polích a důvod od asistenta. Dole volitelná poznámka
 * a dvě tlačítka; poznámku při zamítnutí asistent dostane jako důvod. Uzavřená žádost je jen tichý
 * řádek s výsledkem. Automaticky zamítnutý nástroj (Edit, jiný Bash) se na nic neptá.
 */
export default function ApprovalCard({ approval, onDecide }: { approval: Approval; onDecide: ApprovalDecision }) {
  const [note, setNote] = useState("");
  const open = approval.status === "pending" || approval.status === "sending";
  const target = approval.target;

  if (!target) {
    return (
      <p className="assistant-panel__approval-auto" role="note">
        <span className="assistant-panel__approval-auto-word">{statusWord(approval)}</span>
        {approval.tool}{approval.summary ? `: ${approval.summary}` : ""}
        {approval.reason && <span className="assistant-panel__approval-auto-reason"> · {approval.reason}</span>}
      </p>
    );
  }

  const lines = summaryLines(target.payloadSummary);
  const decide = (decision: "allow" | "deny") => onDecide(approval.id, decision, cleanNote(note));
  return (
    <section
      className={`assistant-panel__approval assistant-panel__approval--${approval.status}`}
      aria-label={`Žádost o zápis: ${targetTitle(target)}`}
    >
      <header className="assistant-panel__approval-head">
        <span className="assistant-panel__approval-kicker">Žádost o zápis na plátno</span>
        <span className="assistant-panel__approval-status" role={open ? undefined : "status"}>{statusWord(approval)}</span>
      </header>
      <p className="assistant-panel__approval-target">{targetTitle(target)}</p>
      <p className="assistant-panel__approval-scope">{targetScope(target)}</p>
      {lines.length > 0 && (
        <ul className="assistant-panel__approval-summary" aria-label="Co se zapíše">
          {lines.map((line, i) => <li key={i} className="assistant-panel__approval-field">{line}</li>)}
        </ul>
      )}
      {approval.reason && <p className="assistant-panel__approval-reason">{approval.reason}</p>}
      {!open && approval.note && <p className="assistant-panel__approval-note">Poznámka: {approval.note}</p>}
      {open && (
        <div className="assistant-panel__approval-actions">
          <textarea
            className="assistant-panel__approval-input"
            rows={2}
            maxLength={NOTE_LIMIT}
            value={note}
            disabled={approval.status === "sending"}
            placeholder="Poznámka pro asistenta (nepovinná; při zamítnutí ji dostane jako důvod)"
            aria-label="Poznámka k rozhodnutí"
            onChange={(e) => setNote(e.target.value)}
          />
          <div className="assistant-panel__approval-buttons">
            <button
              type="button"
              className="assistant-panel__approval-button assistant-panel__approval-button--deny"
              disabled={approval.status === "sending"}
              onClick={() => decide("deny")}
            >
              Zamítnout
            </button>
            <button
              type="button"
              className="assistant-panel__approval-button assistant-panel__approval-button--allow"
              disabled={approval.status === "sending"}
              onClick={() => decide("allow")}
            >
              Povolit
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
