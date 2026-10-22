import { useEffect, useRef, useState } from "react";
import { eventsClient, type EventsSnapshot } from "./events-client";

const EMPTY: EventsSnapshot = { events: [], transport: "connecting", cursor: 0, gaps: 0, error: "" };

/**
 * Odběr sdíleného toku událostí. Každá nová událost karty a každá mezera (`gap`) po krátké pauze znovu
 * načte agent-state (`refresh`), takže tváře karet, Velín i pás drží jeden snímek + deltu.
 */
export function useLiveEvents(project: string, workspace: string, refresh: () => void): EventsSnapshot {
  const key = JSON.stringify([project, workspace]);
  const [state, setState] = useState<EventsSnapshot & { key: string }>({ ...EMPTY, key });
  useEffect(() => eventsClient.subscribe(project, workspace, (next) => setState({ ...next, key })), [key, project, workspace]);
  const shown = state.key === key ? state : { ...EMPTY, key };
  const latest = useRef(refresh);
  latest.current = refresh;
  const seen = useRef({ cursor: shown.cursor, gaps: shown.gaps });
  useEffect(() => {
    const before = seen.current;
    seen.current = { cursor: shown.cursor, gaps: shown.gaps };
    if (shown.transport === "connecting" || (shown.cursor === before.cursor && shown.gaps === before.gaps)) return;
    const timer = window.setTimeout(() => latest.current(), 400);
    return () => window.clearTimeout(timer);
  }, [shown.cursor, shown.gaps, shown.transport]);
  return shown;
}
