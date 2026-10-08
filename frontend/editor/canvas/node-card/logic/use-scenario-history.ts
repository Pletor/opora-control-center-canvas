import { useEffect, useState } from "react";
import { watchQuery } from "@/shared/hooks/logic/query-poll";
import type { NodeWorkflowState } from "@/shared/desktop-state/logic/types";
export type ScenarioHistory = { latest: NodeWorkflowState["scenarioRun"] | null; previous: NodeWorkflowState["scenarioRun"] | null;
  current: boolean; comparable: boolean; deltaPassed: number | null; deltaFailed: number | null };
export function useScenarioHistory(project: string, workspace: string, revision: unknown) {
  const [value, setValue] = useState<{ key: string; nodes?: Record<string, ScenarioHistory>; error?: string } | null>(null);
  const key = JSON.stringify([project, workspace]);
  useEffect(() => {
    if (!project || !workspace) return;
    return watchQuery<{ nodes: Record<string, ScenarioHistory> }>(
      "/api/desktop-v3/scenario-history?" + new URLSearchParams({ project, workspace }), 15000,
      result => setValue({ key, nodes: result.nodes }), error => setValue({ key, error: String(error) }));
  }, [key, project, workspace, revision]);
  return value?.key === key ? value : null;
}
