import { useEffect, useRef } from "react";
import type { Conversation } from "../logic/assistant-events";
import ToolCallRow from "./ToolCallRow";

/** Seznam zpráv: uživatel vpravo, asistent vlevo, mezi nimi sbalené řádky nástrojů a červené chyby. */
export default function MessageList({ conv, loading }: { conv: Conversation; loading: boolean }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "end" }); }, [conv.items, conv.state]);
  const running = conv.state === "running" || conv.state === "waiting_approval";
  return (
    <div className="assistant-panel__messages" role="log" aria-live="polite" aria-label="Konverzace s asistentem">
      {loading && <p className="assistant-panel__hint">Načítám historii…</p>}
      {!loading && conv.items.length === 0 && (
        <p className="assistant-panel__hint">Zeptejte se na plátno, kód nebo další krok. Asistent jen čte a radí, nic nezapisuje.</p>
      )}
      {conv.items.map((item) => {
        if (item.kind === "tool") return <ToolCallRow key={item.id} tool={item} />;
        if (item.kind === "error") return <p key={item.id} role="alert" className="assistant-panel__error">{item.text}</p>;
        return (
          <div key={item.id} className={`assistant-panel__message assistant-panel__message--${item.role}`}>
            <div className="assistant-panel__text">{item.text}</div>
          </div>
        );
      })}
      {running && <p className="assistant-panel__working" role="status">pracuje…</p>}
      {!running && conv.lastTurn && conv.lastTurn.denied > 0 && (
        <p className="assistant-panel__hint">Zamítnuto nástrojů: {conv.lastTurn.denied} (asistent zatím jen čte).</p>
      )}
      <div ref={end} />
    </div>
  );
}
