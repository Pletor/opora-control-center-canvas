import { useState } from "react";
import { api } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import type { NodeWorkflowState } from "@/shared/desktop-state/logic/types";
export type ScenarioHistory = { latest: NodeWorkflowState["scenarioRun"] | null; previous: NodeWorkflowState["scenarioRun"] | null;
  current: boolean; comparable: boolean; deltaPassed: number | null; deltaFailed: number | null };
export function useScenarioHistory(project: string, workspace: string, revision: unknown) {
  const [value, setValue] = useState<{ key: string; nodes?: Record<string, ScenarioHistory>; error?: string } | null>(null);
  const key = JSON.stringify([project, workspace]);
  usePolling(async () => {
    try { const result = await api<{ nodes: Record<string, ScenarioHistory> }>("/api/desktop-v3/scenario-history?" + new URLSearchParams({ project, workspace }));
      setValue({ key, nodes: result.nodes });
    } catch (error) { setValue({ key, error: String(error) }); }
  }, { intervalMs: 15000, enabled: !!project && !!workspace, refreshKeys: [key, revision] });
  return value?.key === key ? value : null;
}
