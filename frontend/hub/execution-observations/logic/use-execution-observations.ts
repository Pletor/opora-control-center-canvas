import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { ObservationRequests, readObservations, type ObservationSnapshot } from "./observations";

type State = { key: string; snapshot: ObservationSnapshot | null; busy: boolean; error: string; loadedAt: number | null };
const emptySnapshot = (): ObservationSnapshot => ({ items: [], readOnly: true, observerConfigured: false, providerAccessVerified: false, usageBasis: "observer-attested-provider-list-cost-not-invoice" });
const empty = (key: string): State => ({ key, snapshot: null, busy: false, error: "", loadedAt: null });
const message = (error: unknown) => error instanceof Error ? error.message : String(error);

/** Read-only scoped data; refresh is explicit so provider usage is never polled or treated as live authority. */
export function useExecutionObservations(project: string, workspace: string, refreshGeneration: number | string = 0, enabled = true) {
  const scope = JSON.stringify([project, workspace]);
  const [attempt, setAttempt] = useState(0);
  const key = JSON.stringify([scope, refreshGeneration, enabled, attempt]);
  const requests = useRef(new ObservationRequests());
  const active = useRef(key);
  if (active.current !== key) { active.current = key; requests.current.invalidate(); }
  const [state, setState] = useState(() => empty(key));
  const shown = state.key === key ? state : empty(key);

  useEffect(() => {
    const valid = requests.current.next();
    if (!enabled || !project || !workspace) { setState(empty(key)); return () => requests.current.invalidate(); }
    setState({ ...empty(key), busy: true });
    readObservations(api, project, workspace).then(snapshot => {
      if (valid()) setState({ key, snapshot, busy: false, error: "", loadedAt: Date.now() });
    }).catch(error => {
      if (valid()) setState({ ...empty(key), error: message(error) });
    });
    return () => requests.current.invalidate();
  }, [key, project, workspace, refreshGeneration, enabled]);

  return { ...(shown.snapshot ?? emptySnapshot()), busy: shown.busy, error: shown.error, project, workspace,
    loadedAt: shown.loadedAt, refresh: () => { requests.current.invalidate(); setAttempt(value => value + 1); } };
}

export type ExecutionObservationsView = ReturnType<typeof useExecutionObservations>;
