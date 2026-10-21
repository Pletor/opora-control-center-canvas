import { ACCESS_REQUIRED_EVENT } from "@/app/access-gate/logic/access-gate";
import { createPoller } from "@/shared/hooks/logic/poller";
import { parseProcess, processEndpoint, type ProcessSnapshot } from "./process-sync";

export type ProcessState = { snapshot: ProcessSnapshot | null; busy: boolean; error: string };
export const emptyProcess = (): ProcessState => ({ snapshot: null, busy: false, error: "" });
export async function readProcess(project: string, workspace: string, signal: AbortSignal): Promise<ProcessSnapshot> {
  const response = await fetch(processEndpoint(project, workspace), { signal, cache: "no-store", redirect: "error" });
  if (response.status === 401 && typeof window !== "undefined") window.dispatchEvent(new Event(ACCESS_REQUIRED_EVENT));
  if (!response.ok) throw new Error(`Proces není dostupný (HTTP ${response.status}).`);
  const raw = await response.text();
  if (raw.length > 1024 * 1024) throw new Error("Odpověď procesu překročila povolenou velikost.");
  return parseProcess(JSON.parse(raw), project, workspace);
}
export type ProcessEnvironment = {
  visible(): boolean; listen(event: "focus" | "visibilitychange", callback: () => void): () => void;
};
export function browserProcessEnvironment(): ProcessEnvironment {
  return { visible: () => document.visibilityState !== "hidden", listen: (event, callback) => {
    const target = event === "focus" ? window : document;
    target.addEventListener(event, callback); return () => target.removeEventListener(event, callback);
  } };
}
/** One scoped read lifetime. Aborted or superseded responses cannot publish, even if transport ignores abort. */
export function watchProcess(project: string, workspace: string, publish: (state: ProcessState) => void,
  environment: ProcessEnvironment, read = readProcess) {
  let generation = 0, closed = false, controller: AbortController | undefined;
  let latest: ProcessSnapshot | null = null;
  const invalidate = () => { generation++; controller?.abort(); controller = undefined; };
  const run = async () => {
    if (closed || !project || !workspace || !environment.visible()) return;
    invalidate(); const current = generation;
    controller = new AbortController(); publish({ snapshot: latest, busy: true, error: "" });
    await read(project, workspace, controller.signal).then(snapshot => {
      if (!closed && current === generation) { latest = snapshot; publish({ snapshot, busy: false, error: "" }); }
    }).catch(() => {
      if (!closed && current === generation) publish({ snapshot: latest, busy: false, error: "Proces se nepodařilo načíst. Obnovte podklady." });
    });
  };
  const poller = createPoller({ run, intervalMs: 15000, visibility: {
    hidden: () => !environment.visible(), subscribe: changed => environment.listen("visibilitychange", () => {
      const inflight = poller.running();
      if (!environment.visible()) invalidate();
      changed();
      // A request invalidated while hidden is not a fresh read on return.
      if (environment.visible() && inflight) void poller.refresh();
    }),
  } });
  const unlisten = environment.listen("focus", () => {
    if (!closed && environment.visible()) void poller.poke();
  });
  poller.start();
  return { refresh: () => {
    if (closed || !environment.visible()) return;
    invalidate(); void poller.refresh();
  }, close: () => { closed = true; invalidate(); poller.stop(); unlisten(); } };
}
