import { useEffect, useRef, useState } from "react";
import { isBusy, type Conversation as ConversationState } from "../logic/assistant-events";
import { formatElapsed } from "../logic/task-overview";
import type { Turn } from "../logic/turns";
import { useActiveTurn } from "../logic/use-active-turn";
import type { ApprovalDecision } from "./ApprovalCard";
import TurnBlock from "./TurnBlock";

/** Hodiny tahu: od chvíle, kdy panel uviděl běh, tikají po sekundě; po doběhnutí zmizí. */
function useElapsed(running: boolean): number {
  const [start, setStart] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running) { setStart(null); return; }
    setStart((s) => s ?? Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [running]);
  return start === null ? 0 : Math.max(0, now - start);
}

/**
 * Konverzace jako dokument členěný po tazích: každý tah má hlavičku, pod ní zprávu uživatele, kroky
 * nástrojů a odpověď; na konci „pracuje… 0:12“. Posouvá se ke konci jen tehdy, když uživatel už u konce
 * je, aby ho při čtení starší odpovědi nový text netahal dolů. Který tah se právě čte, hlásí nahoru.
 */
export default function Conversation({
  conv,
  turns,
  loading,
  sessionKey,
  onActiveTurn,
  onDecide,
}: {
  conv: ConversationState;
  turns: Turn[];
  loading: boolean;
  sessionKey: string;
  onActiveTurn: (anchor: string | null) => void;
  onDecide: ApprovalDecision;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const running = isBusy(conv.state);
  const elapsed = useElapsed(running);
  useActiveTurn(scroller, turns.map((t) => t.anchor), onActiveTurn);

  useEffect(() => { stick.current = true; }, [sessionKey]);
  useEffect(() => {
    const el = scroller.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [conv.items, running, loading]);

  return (
    <div
      ref={scroller}
      className="assistant-panel__conversation"
      onScroll={(e) => {
        const el = e.currentTarget;
        stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
      }}
    >
      <div className="assistant-panel__column" role="log" aria-live="polite" aria-label="Konverzace s asistentem">
        {loading && <p className="assistant-panel__hint">Načítám historii…</p>}
        {!loading && turns.length === 0 && (
          <p className="assistant-panel__hint">
            Zeptejte se na plátno, kód nebo další krok. Asistent čte a radí; na plátno zapíše jen s vaším schválením.
          </p>
        )}
        {turns.map((turn) => <TurnBlock key={turn.anchor} turn={turn} onDecide={onDecide} />)}
        {running && (
          <p className="assistant-panel__working" role="status">
            <span className="assistant-panel__working-pulse" aria-hidden="true" />
            {conv.state === "waiting_approval" ? "čeká na vás…" : "pracuje…"} <span className="assistant-panel__working-time">{formatElapsed(elapsed)}</span>
          </p>
        )}
        {!running && conv.lastTurn && conv.lastTurn.denied > 0 && (
          <p className="assistant-panel__hint">Zamítnuto nástrojů: {conv.lastTurn.denied} (kód asistent nemění, na plátno zapisuje jen se schválením).</p>
        )}
      </div>
    </div>
  );
}
