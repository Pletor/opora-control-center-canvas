import { useEffect, useState } from "react";
import { watchQuery } from "@/shared/hooks/logic/query-poll";
export type WorkStatus = "waiting" | "claimed" | "waiting-human" | "proposed" | "done" | "blocked";
export type WorkRow = { id: string; name: string; status: WorkStatus; agent: string; startedAt: string | null; lastActivity: string | null;
  touched: string[] | null; waitingOnHuman: { blockId: string; ask: string }[]; blockedBy: { id: string; name: string }[] };
export type WorkOverview = { nodes: Record<string, WorkRow>; sectors: Record<string, Record<WorkStatus, number>> };
export function useWorkOverview(project: string, workspace: string, revision: unknown) {
  const [value, setValue] = useState<{ key: string; data?: WorkOverview; error?: string } | null>(null);
  const key = JSON.stringify([project, workspace]);
  useEffect(() => {
    if (!project || !workspace) return;
    return watchQuery<WorkOverview>(
      "/api/desktop-v3/work-overview?" + new URLSearchParams({ project, workspace }), 15000,
      data => setValue({ key, data }), error => setValue({ key, error: String(error) }));
  }, [project, workspace, key, revision]);
  return value?.key === key ? value : null;
}
