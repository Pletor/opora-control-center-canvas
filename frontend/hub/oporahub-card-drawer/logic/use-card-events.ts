import { useCallback, useEffect, useState } from "react";
import { hubRead } from "@/hub/oporahub-mirror/logic/hub-read";
import { eventsUrl, parseEventPage, readCardEvents, type HubEvent } from "../history-tab/logic/card-events";

export type CardEvents = { events: HubEvent[]; head: number; truncated: boolean; gap: boolean; busy: boolean; error: string; reload: () => void };

/** Události jedné karty (stránkováno kurzorem, filtr karty na klientovi); čte se při otevření a po obnově. */
export function useCardEvents(project: string, workspace: string, nodeId: string): CardEvents {
  const key = JSON.stringify([project, workspace, nodeId]);
  const [nonce, setNonce] = useState(0);
  const [state, setState] = useState({ key, events: [] as HubEvent[], head: 0, truncated: false, gap: false, busy: false, error: "" });
  useEffect(() => {
    if (!project || !workspace || !nodeId) return;
    const controller = new AbortController();
    setState(current => ({ ...(current.key === key ? current : { events: [], head: 0, truncated: false, gap: false }), key, busy: true, error: "" }));
    readCardEvents(since => hubRead(eventsUrl(project, workspace, since), parseEventPage, controller.signal), nodeId)
      .then(result => { if (!controller.signal.aborted) setState({ key, ...result, busy: false, error: "" }); })
      .catch(error => { if (!controller.signal.aborted) setState(current => ({ ...current, key, busy: false,
        error: error instanceof Error ? error.message : "Události se nepodařilo načíst." })); });
    return () => controller.abort();
  }, [key, nonce, project, workspace, nodeId]);
  const reload = useCallback(() => setNonce(value => value + 1), []);
  const shown = state.key === key ? state : { key, events: [], head: 0, truncated: false, gap: false, busy: true, error: "" };
  return { events: shown.events, head: shown.head, truncated: shown.truncated, gap: shown.gap, busy: shown.busy, error: shown.error, reload };
}
