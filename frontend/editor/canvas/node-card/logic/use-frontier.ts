import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";

export type FrontierRow = { id: string; name: string; claim?: string; blockedBy?: { id: string; name: string }[]; waitingOnHuman?: { blockId: string; ask: string }[] };
export type FrontierItem = FrontierRow & { status: "frontier" | "claimed" | "blocked" | "waiting" | "closed" };
export function useFrontier(scope: { project: string; workspace: string } | undefined, parent: string | null, enabled: boolean, revision: unknown) {
  const [value, setValue] = useState<{ key: string; rows: Record<string, FrontierItem> } | null>(null);
  const [error, setError] = useState("");
  const key = JSON.stringify([scope?.project, scope?.workspace, parent]);
  useEffect(() => {
    if (!enabled || !scope) return;
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    const params = new URLSearchParams({ ...scope, nodeId: parent ?? "" });
    async function refresh() {
      try {
        const result = await api<Record<FrontierItem["status"], FrontierRow[]>>("/api/desktop-v3/frontier?" + params);
        const rows: Record<string, FrontierItem> = {};
        for (const status of ["frontier", "claimed", "blocked", "waiting", "closed"] as const) {
          for (const row of result[status]) rows[row.id] = { ...row, status };
        }
        if (live) { setValue({ key, rows }); setError(""); }
      } catch (e) { if (live) { setValue(null); setError(String(e)); } }
      if (live) timer = setTimeout(refresh, 15000);
    }
    void refresh();
    return () => { live = false; clearTimeout(timer); };
  }, [key, enabled, revision]);
  return { rows: enabled && value?.key === key ? value.rows : undefined, error: enabled ? error : "" };
}
