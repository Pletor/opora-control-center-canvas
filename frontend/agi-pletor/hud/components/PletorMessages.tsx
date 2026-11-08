import { useEffect, useRef } from "react";
import type { PletorMessage } from "../logic/pletor-client";

/** Seznam zpráv: člověk vpravo, Pletor vlevo, odpověď srdce vlevo se štítkem „Srdce“; nová zpráva odroluje dolů. */
export default function PletorMessages({ messages, sending }: { messages: PletorMessage[]; sending: boolean }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "end" }); }, [messages.length, sending]);
  return (
    <div className="pletor__messages" role="log" aria-live="polite">
      {messages.length === 0 && <p className="pletor__empty">Řekni Pletorovi záměr, prioritu nebo rozhodnutí. Srdci ho předá on.</p>}
      {messages.map((message, index) => (
        <p key={index} className={`pletor__message pletor__message--${message.role}`}>
          {message.role === "heart" && <span className="pletor__message-label">Srdce</span>}{message.text}
        </p>
      ))}
      {sending && <p className="pletor__message pletor__message--pletor pletor__message--pending">Přemýšlí<span className="pletor__dots" aria-hidden="true"><i /><i /><i /></span></p>}
      <div ref={end} />
    </div>
  );
}
