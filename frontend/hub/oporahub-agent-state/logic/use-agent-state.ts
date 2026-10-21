import { useEffect, useRef, useState } from "react";
import { browserReaderEnvironment, emptyAgentState, watchAgentState, type AgentStateSnapshot } from "./agent-state-reader";

/** Jediné periodické čtení přehledu OporaHubu; změna scope okamžitě skryje data předchozího prostoru. */
export function useAgentState(project: string, workspace: string) {
  const key = JSON.stringify([project, workspace]);
  const [state, setState] = useState<AgentStateSnapshot & { key: string }>(() => ({ ...emptyAgentState(), key }));
  const watcher = useRef<{ key: string; reader: ReturnType<typeof watchAgentState> } | null>(null);
  useEffect(() => {
    const reader = watchAgentState(project, workspace, next => setState({ ...next, key }), browserReaderEnvironment());
    const current = { key, reader }; watcher.current = current;
    return () => { reader.close(); if (watcher.current === current) watcher.current = null; };
  }, [key, project, workspace]);
  const shown = state.key === key ? state : { ...emptyAgentState(), key };
  return { ...shown, refresh: () => { if (watcher.current?.key === key) watcher.current.reader.refresh(); } };
}
export type AgentStateView = ReturnType<typeof useAgentState>;
