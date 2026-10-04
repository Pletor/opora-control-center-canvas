import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Graph, type View } from "@/shared/types/logic/types";

type Snapshot = { scope: string; view: View };
export type ArchitecturePlanResult = { view: View; refs: Record<string, string> };

/** Own editor lifecycle; mutations still use the existing atomic graph APIs. */
export function useArchitectureGraph(project: string, workspace: string, onGraphChanged?: () => void) {
  const scope = JSON.stringify([project, workspace]);
  const lifecycle = useRef({ scope, generation: 0, mounted: true });
  if (lifecycle.current.scope !== scope) lifecycle.current = { scope, generation: lifecycle.current.generation + 1, mounted: true };
  const lock = useRef<number | null>(null);
  const reads = useRef(0);
  const current = useRef<Snapshot | null>(null);
  const notify = useRef(onGraphChanged);
  notify.current = onGraphChanged;
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const clearError = useCallback(() => setError(null), []);
  const url = `/api/view?${new URLSearchParams({ project, workspace })}`;
  const active = useCallback((generation: number) => lifecycle.current.mounted && lifecycle.current.scope === scope && lifecycle.current.generation === generation, [scope]);
  const accept = useCallback((view: View) => {
    const value = { scope, view };
    current.current = value;
    setSnapshot(value);
  }, [scope]);

  const reload = useCallback(async (): Promise<View> => {
    const generation = lifecycle.current.generation;
    if (!active(generation)) throw new Error("Rozsah editoru se změnil.");
    if (lock.current === generation) throw new Error("Počkejte na dokončení ukládání.");
    const request = ++reads.current;
    setLoading(true);
    setError(null);
    try {
      const view = await api<View>(url);
      if (!active(generation) || request !== reads.current) throw new Error("Rozsah editoru se změnil nebo byl znovu načten.");
      accept(view);
      return view;
    } catch (cause) {
      if (active(generation) && request === reads.current) setError(cause instanceof Error ? cause.message : String(cause));
      throw cause;
    } finally {
      if (active(generation) && request === reads.current) setLoading(false);
    }
  }, [active, accept, url]);

  useEffect(() => {
    lifecycle.current.mounted = true;
    lock.current = null;
    current.current = null;
    setSnapshot(null);
    setBusy(false);
    void reload().catch(() => undefined);
    return () => { lifecycle.current.mounted = false; lifecycle.current.generation += 1; };
  }, [reload]);

  const mutate = useCallback(async (path: string, body: object, expectedDigest: string): Promise<ArchitecturePlanResult> => {
    const generation = lifecycle.current.generation;
    let acquired = false;
    let accepted = false;
    try {
      if (!active(generation)) throw new Error("Rozsah editoru se změnil.");
      if (lock.current === generation) throw new Error("Počkejte na dokončení ukládání.");
      const loaded = current.current?.scope === scope ? current.current.view : null;
      if (!loaded) throw new Error("Nejprve načtěte plátno.");
      if (loaded.readOnly) throw new Error("Tento pracovní prostor je pouze pro čtení.");
      if (!expectedDigest || expectedDigest !== loaded.digest) throw new Error("Plátno se změnilo. Obnovte je před dalším uložením.");
      lock.current = generation;
      acquired = true;
      ++reads.current; // A preceding reload cannot overwrite this mutation's result.
      setLoading(false);
      setBusy(true);
      setError(null);
      let view: View;
      let refs: Record<string, string> = {};
      if (path === "/api/canvas-plan") {
        const result = await api<{ ok?: boolean; dryRun?: boolean; refs?: unknown }>(path, { project, workspace, digest: expectedDigest, ...body });
        if (result?.ok !== true || result.dryRun !== false) throw new Error("Server nepotvrdil uložení plánu. Před opakováním obnovte plátno.");
        accepted = true;
        if (!result.refs || typeof result.refs !== "object" || Array.isArray(result.refs) || Object.values(result.refs).some((id) => typeof id !== "string" || !/^[A-Za-z0-9_-]{1,80}$/.test(id))) throw new Error("Server nevrátil platné identity vytvořených prvků.");
        refs = result.refs as Record<string, string>;
        view = await api<View>(url);
        if (Object.values(refs).some((id) => !view.graph.nodes.some((node) => node.id === id))) throw new Error("Načtené plátno neobsahuje vytvořené prvky.");
      } else {
        view = await api<View>(path, { project, workspace, digest: expectedDigest, ...body });
        accepted = true;
      }
      if (!active(generation)) throw new Error("Rozsah editoru se během ukládání změnil.");
      accept(view);
      notify.current?.();
      return { view, refs };
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : String(cause);
      const failure = new Error(accepted ? `Zápis byl přijat, ale dokončení nelze potvrdit. Nevkládejte stejné prvky znovu; obnovte plátno. ${detail}` : detail);
      if (active(generation)) {
        setError(failure.message);
        if (accepted) { current.current = null; setSnapshot(null); }
      }
      throw failure;
    } finally {
      if (acquired && active(generation)) { lock.current = null; setBusy(false); }
    }
  }, [active, accept, project, workspace, scope, url]);

  const saveGraph = useCallback(async (graph: Graph, expectedDigest: string): Promise<View> => (await mutate("/api/graph", { graph }, expectedDigest)).view, [mutate]);
  const applyPlan = useCallback((plan: object, expectedDigest: string): Promise<ArchitecturePlanResult> => mutate("/api/canvas-plan", { plan }, expectedDigest), [mutate]);
  return { view: snapshot?.scope === scope ? snapshot.view : null, loading, busy, error, clearError, reload, saveGraph, applyPlan };
}
