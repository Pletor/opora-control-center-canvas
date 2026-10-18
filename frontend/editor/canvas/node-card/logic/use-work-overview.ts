import { useState } from "react";
import { api } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { keepSame } from "@/shared/hooks/logic/same-response";
export type WorkStatus = "waiting" | "claimed" | "waiting-human" | "proposed" | "done" | "blocked";
export type WorkRow = { id: string; name: string; status: WorkStatus; agent: string; startedAt: string | null; lastActivity: string | null;
  touched: string[] | null; waitingOnHuman: { blockId: string; ask: string }[]; blockedBy: { id: string; name: string }[] };
export type WorkOverview = { nodes: Record<string, WorkRow>; sectors: Record<string, Record<WorkStatus, number>> };
export function useWorkOverview(project: string, workspace: string, revision: unknown) {
  const [value, setValue] = useState<{ key: string; data?: WorkOverview; error?: string } | null>(null);
  const key = JSON.stringify([project, workspace]);
  usePolling(async () => {
    try {
      const data = await api<WorkOverview>("/api/desktop-v3/work-overview?" + new URLSearchParams({ project, workspace }));
      setValue((current) => keepSame(current, { key, data }));
    } catch (error) { setValue((current) => keepSame(current, { key, error: String(error) })); }
  }, { intervalMs: 15000, enabled: !!project && !!workspace, refreshKeys: [key], debouncedKeys: [revision] });
  return value?.key === key ? value : null;
}
