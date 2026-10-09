import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
import type { NodeWorkflowState } from "@/shared/desktop-state/logic/types";
export type ScenarioHistory = { latest: NodeWorkflowState["scenarioRun"] | null; previous: NodeWorkflowState["scenarioRun"] | null;
  current: boolean; comparable: boolean; deltaPassed: number | null; deltaFailed: number | null };
export function useScenarioHistory(project: string, workspace: string, revision: unknown) {
  const [value, setValue] = useState<{ key: string; nodes?: Record<string, ScenarioHistory>; error?: string } | null>(null);
  const key = JSON.stringify([project, workspace]);
  useEffect(() => {
    if (!project || !workspace) return;
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try { const result = await api<{ nodes: Record<string, ScenarioHistory> }>("/api/desktop-v3/scenario-history?" + new URLSearchParams({ project, workspace }));
        if (live) setValue({ key, nodes: result.nodes });
      } catch (error) { if (live) setValue({ key, error: String(error) }); }
      if (live) timer = setTimeout(refresh, 15000);
    }
    void refresh();
    return () => { live = false; clearTimeout(timer); };
  }, [key, project, workspace, revision]);
  return value?.key === key ? value : null;
}
