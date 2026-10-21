import { ACCESS_REQUIRED_EVENT } from "@/app/access-gate/logic/access-gate";
import { createPoller } from "@/shared/hooks/logic/poller";
import { readAgentState, type AgentState, type AgentStateRead } from "./agent-state";

export const AGENT_STATE_INTERVAL_MS = 10000;
export type AgentStateSnapshot = { state: AgentState | null; etag: string; busy: boolean; error: string; loadedAt: number };
export const emptyAgentState = (): AgentStateSnapshot => ({ state: null, etag: "", busy: false, error: "", loadedAt: 0 });
export type ReaderEnvironment = { visible(): boolean; now(): number; listen(callback: () => void): () => void };
export function browserReaderEnvironment(): ReaderEnvironment {
  return { visible: () => document.visibilityState !== "hidden", now: () => Date.now(), listen: callback => {
    document.addEventListener("visibilitychange", callback); return () => document.removeEventListener("visibilitychange", callback);
  } };
}
type Read = (project: string, workspace: string, etag: string, signal: AbortSignal) => Promise<AgentStateRead>;
const guardedRead: Read = async (project, workspace, etag, signal) => {
  try { return await readAgentState(project, workspace, etag, signal); } catch (error) {
    if (String(error).includes("HTTP 401") && typeof window !== "undefined") window.dispatchEvent(new Event(ACCESS_REQUIRED_EVENT));
    throw error;
  }
};

/** Jedno čtení pro celý prostor: poller nikdy nepřekrývá dotazy a 304 jen potvrdí čerstvost snímku. */
export function watchAgentState(project: string, workspace: string, publish: (snapshot: AgentStateSnapshot) => void,
  environment: ReaderEnvironment, read: Read = guardedRead) {
  let generation = 0, closed = false, controller: AbortController | undefined;
  let latest = emptyAgentState();
  const emit = (next: Partial<AgentStateSnapshot>) => { latest = { ...latest, ...next }; publish(latest); };
  const invalidate = () => { generation++; controller?.abort(); controller = undefined; };
  const run = async () => {
    if (closed || !project || !workspace || !environment.visible()) return;
    invalidate(); const current = generation;
    controller = new AbortController(); emit({ busy: true });
    await read(project, workspace, latest.etag, controller.signal).then(result => {
      if (closed || current !== generation) return;
      if (result.kind === "unchanged") emit({ busy: false, error: "", loadedAt: environment.now() });
      else emit({ state: result.state, etag: result.etag, busy: false, error: "", loadedAt: environment.now() });
    }).catch(error => {
      if (closed || current !== generation) return;
      emit({ busy: false, error: error instanceof Error ? error.message : "Stav pro agenty se nepodařilo načíst." });
    });
  };
  const poller = createPoller({ run, intervalMs: AGENT_STATE_INTERVAL_MS, visibility: {
    hidden: () => !environment.visible(), subscribe: changed => environment.listen(() => { if (!environment.visible()) invalidate(); changed(); }),
  } });
  poller.start();
  return {
    refresh: () => { if (!closed) { invalidate(); void poller.refresh(); } },
    close: () => { closed = true; invalidate(); poller.stop(); },
  };
}
