import { useState } from "react";
import type { Escalation } from "../logic/heart-api";
import { clock } from "../logic/heart-status";

/** Jedna otázka srdce: text, pole odpovědi a Odpovědět. Rozepsanou odpověď drží jen do odeslání. */
function EscalationItem({ escalation, onAnswer }: { escalation: Escalation; onAnswer: (ticketId: string, text: string) => Promise<boolean> }) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const submit = async () => {
    if (!text.trim() || sending) return;
    setSending(true);
    if (await onAnswer(escalation.ticketId, text.trim())) setText("");
    setSending(false);
  };
  return (
    <li className="heart-channel__escalation">
      <p className="heart-channel__escalation-text">{escalation.text}</p>
      <span className="heart-channel__escalation-meta">{clock(escalation.createdAt)}</span>
      <form className="heart-channel__escalation-form" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
        <textarea
          className="heart-channel__field"
          rows={2}
          value={text}
          aria-label={`Odpověď na otázku: ${escalation.text}`}
          placeholder="Vaše odpověď…"
          onChange={(event) => setText(event.target.value)}
        />
        <button type="submit" className="heart-channel__button" disabled={!text.trim() || sending}>Odpovědět</button>
      </form>
    </li>
  );
}

/** Čeká na vás: otevřené otázky srdce, od nejnovější. Bez odpovědi zůstane plán srdce stát. */
export default function Escalations({ escalations, onAnswer }: { escalations: Escalation[]; onAnswer: (ticketId: string, text: string) => Promise<boolean> }) {
  return (
    <section className="heart-channel__section" aria-label="Čeká na vás">
      <h3 className="heart-channel__heading">
        Čeká na vás {escalations.length > 0 && <span className="heart-channel__count">{escalations.length}</span>}
      </h3>
      {escalations.length === 0 ? (
        <p className="heart-channel__empty">Srdce se teď na nic neptá.</p>
      ) : (
        <ul className="heart-channel__escalations">
          {escalations.map((escalation) => (
            <EscalationItem key={escalation.ticketId} escalation={escalation} onAnswer={onAnswer} />
          ))}
        </ul>
      )}
    </section>
  );
}
