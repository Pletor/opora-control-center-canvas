import { useEffect, useMemo, useRef, useState } from "react";
import { isBusy, type Conversation as ConversationState } from "../logic/assistant-events";
import { formatElapsed } from "../logic/task-overview";
import { groupEntries } from "../logic/tool-steps";
import MessageBlock from "./MessageBlock";
import ToolSteps from "./ToolSteps";

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
 * Konverzace jako dokument: zprávy pod sebou s velkou mezerou, kroky nástrojů sbalené do řádku a na
 * konci „pracuje… 0:12“. Posouvá se ke konci jen tehdy, když uživatel už u konce je, aby ho při čtení
 * starší odpovědi nový text netahal dolů.
 */
export default function Conversation({ conv, loading, sessionKey }: { conv: ConversationState; loading: boolean; sessionKey: string }) {
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const entries = useMemo(() => groupEntries(conv.items), [conv.items]);
  const running = isBusy(conv.state);
  const elapsed = useElapsed(running);

  useEffect(() => { stick.current = true; }, [sessionKey]);
  useEffect(() => {
    const el = scroller.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [entries, running, loading]);

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
        {!loading && entries.length === 0 && (
          <p className="assistant-panel__hint">
            Zeptejte se na plátno, kód nebo další krok. Asistent jen čte a radí, nic nezapisuje.
          </p>
        )}
        {entries.map((entry) => {
          if (entry.kind === "steps") return <ToolSteps key={entry.id} tools={entry.tools} />;
          if (entry.kind === "error") return <p key={entry.item.id} role="alert" className="assistant-panel__error">{entry.item.text}</p>;
          return <MessageBlock key={entry.item.id} message={entry.item} />;
        })}
        {running && (
          <p className="assistant-panel__working" role="status">
            <span className="assistant-panel__working-pulse" aria-hidden="true" />
            {conv.state === "waiting_approval" ? "čeká na vás…" : "pracuje…"} <span className="assistant-panel__working-time">{formatElapsed(elapsed)}</span>
          </p>
        )}
        {!running && conv.lastTurn && conv.lastTurn.denied > 0 && (
          <p className="assistant-panel__hint">Zamítnuto nástrojů: {conv.lastTurn.denied} (asistent zatím jen čte).</p>
        )}
      </div>
    </div>
  );
}
