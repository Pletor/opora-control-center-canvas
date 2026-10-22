import { useEffect, useRef, useState } from "react";
import { emptyAgentState, type AgentStateSnapshot } from "./agent-state-reader";
import { agentStateStore } from "./agent-state-store";

/** Odběr sdíleného čtení agent-state (přehled i plátno); změna scope okamžitě skryje data předchozího prostoru. */
export function useAgentState(project: string, workspace: string) {
  const key = JSON.stringify([project, workspace]);
  const [state, setState] = useState<AgentStateSnapshot & { key: string }>(() => ({ ...emptyAgentState(), key }));
  const watcher = useRef<{ key: string; refresh: () => void } | null>(null);
  useEffect(() => {
    const subscription = agentStateStore.subscribe(project, workspace, next => setState({ ...next, key }));
    const current = { key, refresh: subscription.refresh }; watcher.current = current;
    return () => { subscription.close(); if (watcher.current === current) watcher.current = null; };
  }, [key, project, workspace]);
  const shown = state.key === key ? state : { ...emptyAgentState(), key };
  return { ...shown, refresh: () => { if (watcher.current?.key === key) watcher.current.refresh(); } };
}
export type AgentStateView = ReturnType<typeof useAgentState>;
