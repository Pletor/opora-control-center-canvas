// Data plátna srdce: workflow srdce projektu, jeho verze, registr typů uzlů, běhy a prostoje. Běhy a prostoje se
// obnovují každých 5 s (srdce běží samo podle rozvrhu); verze jen po vlastním zápisu (`reload`).
import { useCallback, useEffect, useState } from "react";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import type { FlowRun, FlowVersion, FlowWorkflow, NodeTypeSpec, Stall } from "@/shared/flow-editor/logic/flow-types";
import { loadNodeTypes, loadRuns, loadStalls, loadVersions, loadWorkflows, pickHeartWorkflow } from "./heart-api";

export type HeartData = {
  workflow: FlowWorkflow | null; versions: FlowVersion[]; types: NodeTypeSpec[]; runs: FlowRun[]; stalls: Stall[];
  loading: boolean; error: string; reload: () => void;
};
const POLL_MS = 5000;
const text = (error: unknown) => error instanceof Error ? error.message : String(error);

export function useHeartData(project: string): HeartData {
  const [workflow, setWorkflow] = useState<FlowWorkflow | null>(null);
  const [versions, setVersions] = useState<FlowVersion[]>([]);
  const [types, setTypes] = useState<NodeTypeSpec[]>([]);
  const [runs, setRuns] = useState<FlowRun[]>([]);
  const [stalls, setStalls] = useState<Stall[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tick, setTick] = useState(0);
  const reload = useCallback(() => setTick((value) => value + 1), []);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    Promise.all([loadWorkflows(project), loadNodeTypes()]).then(async ([workflows, registry]) => {
      const heart = pickHeartWorkflow(workflows, project);
      const list = heart ? await loadVersions(heart.id) : [];
      if (!alive) return;
      setWorkflow(heart); setTypes(registry); setVersions(list); setError("");
    }).catch((reason) => { if (alive) setError(text(reason)); }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [project, tick]);

  const workflowId = workflow?.id;
  usePolling(async () => {
    if (!workflowId) return;
    try {
      const [nextRuns, nextStalls] = await Promise.all([loadRuns(workflowId), loadStalls()]);
      setRuns(nextRuns); setStalls(nextStalls);
    } catch (reason) { setError(text(reason)); }
  }, { intervalMs: POLL_MS, enabled: !!workflowId, refreshKeys: [workflowId] });

  return { workflow, versions, types, runs, stalls, loading, error, reload };
}
