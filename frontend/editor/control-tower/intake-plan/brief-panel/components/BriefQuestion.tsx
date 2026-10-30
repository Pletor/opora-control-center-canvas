// Jedna otázka výslechu: co srdce potřebuje vědět, co samo doporučuje a proč. Člověk buď jedním klikem potvrdí
// doporučení, nebo rozbalí textové pole a odpoví jinak. Rozepsaný text drží dílek; odeslání hlásí `onAnswer` nahoru
// (null = potvrzené doporučení) a zpět dostane `busy` a `error`.
import { useState } from "react";
import type { BriefOpenQuestion } from "../logic/brief-model";

type Props = { question: BriefOpenQuestion; busy: boolean; error: string | null; onAnswer: (answer: string | null) => void };

export default function BriefQuestion({ question, busy, error, onAnswer }: Props) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  const ready = text.trim().length > 0;
  return (
    <li className="brief-panel__question" data-oh-question={question.id}>
      <p className="brief-panel__ask">{question.text}</p>
      {question.recommended && <p className="brief-panel__recommended">
        <span className="brief-panel__label">Srdce doporučuje</span>{question.recommended}
      </p>}
      {question.why && <p className="brief-panel__why">Proč: {question.why}</p>}
      {!editing && <div className="brief-panel__actions">
        {question.recommended && <button type="button" className="brief-panel__button brief-panel__button--primary" disabled={busy}
          onClick={() => onAnswer(null)} data-oh-action="accept">Potvrdit doporučení</button>}
        <button type="button" className="brief-panel__button" disabled={busy} onClick={() => setEditing(true)}
          data-oh-action="answer-other">Odpovědět jinak</button>
      </div>}
      {editing && <form className="brief-panel__form" onSubmit={event => { event.preventDefault(); if (ready) onAnswer(text.trim()); }}>
        <textarea className="brief-panel__input" value={text} rows={3} maxLength={500} disabled={busy}
          aria-label={`Vaše odpověď: ${question.text}`} placeholder="Napište, jak to má být a proč."
          onChange={event => setText(event.target.value)} />
        <div className="brief-panel__actions">
          <button type="submit" className="brief-panel__button brief-panel__button--primary" disabled={busy || !ready}>Odeslat</button>
          <button type="button" className="brief-panel__button" disabled={busy} onClick={() => setEditing(false)}>Zpět</button>
        </div>
      </form>}
      {busy && <small className="brief-panel__muted">Posílám odpověď srdci…</small>}
      {error && <p className="brief-panel__error" role="alert">{error}</p>}
    </li>
  );
}
