import { useEffect, useMemo, useState } from "react";
import { useLiveEvents } from "@/editor/live-strip/logic/use-live-events";
import { toFlowEvent } from "./process-event";
import { emptyBuffer, ingest, pause, resume, type StreamBuffer } from "./stream-buffer";

/**
 * Odběr sdíleného toku (stejné spojení jako živý pás Editoru: Last-Event-ID, `gap` → nové čtení agent-state,
 * polling jako pojistka). Mapa vidí vždy všechny události; proud vidí jen `shown`, dokud je čtení pozastavené.
 */
export function useProcessStream(project: string, workspace: string, refreshAgentState: () => void) {
  const live = useLiveEvents(project, workspace, refreshAgentState);
  const events = useMemo(() => live.events.map(toFlowEvent), [live.events]);
  const key = JSON.stringify([project, workspace]);
  const [buffer, setBuffer] = useState<StreamBuffer & { key: string }>({ ...emptyBuffer(), key });
  useEffect(() => {
    setBuffer((current) => {
      const base = current.key === key ? current : { ...emptyBuffer(), key };
      const next = ingest(base, events);
      return next === base ? base : { ...next, key };
    });
  }, [events, key]);
  const shown = buffer.key === key ? buffer : { ...emptyBuffer(), key };
  return {
    events, transport: live.transport, error: live.error, buffer: shown,
    togglePause: () => setBuffer((current) => ({ ...(current.paused ? resume(current) : pause(current)), key: current.key })),
  };
}
