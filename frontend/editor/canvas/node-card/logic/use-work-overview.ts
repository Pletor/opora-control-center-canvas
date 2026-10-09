import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
export type WorkStatus = "waiting" | "claimed" | "waiting-human" | "proposed" | "done" | "blocked";
export type WorkRow = { id: string; name: string; status: WorkStatus; agent: string; startedAt: string | null; lastActivity: string | null;
  touched: string[] | null; waitingOnHuman: { blockId: string; ask: string }[]; blockedBy: { id: string; name: string }[] };
export type WorkOverview = { nodes: Record<string, WorkRow>; sectors: Record<string, Record<WorkStatus, number>> };
export function useWorkOverview(project: string, workspace: string, revision: unknown) {
  const [value, setValue] = useState<{ key: string; data?: WorkOverview; error?: string } | null>(null);
  const key = JSON.stringify([project, workspace]);
  useEffect(() => {
    if (!project || !workspace) return;
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const data = await api<WorkOverview>("/api/desktop-v3/work-overview?" + new URLSearchParams({ project, workspace }));
        if (live) setValue({ key, data });
      } catch (error) { if (live) setValue({ key, error: String(error) }); }
      if (live) timer = setTimeout(refresh, 15000);
    }
    void refresh();
    return () => { live = false; clearTimeout(timer); };
  }, [project, workspace, key, revision]);
  return value?.key === key ? value : null;
}
