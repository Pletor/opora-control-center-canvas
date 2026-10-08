import { useEffect, useState } from "react";
import { watchQuery } from "@/shared/hooks/logic/query-poll";

export type FrontierRow = { id: string; name: string; claim?: string; blockedBy?: { id: string; name: string }[]; waitingOnHuman?: { blockId: string; ask: string }[] };
export type FrontierItem = FrontierRow & { status: "frontier" | "claimed" | "blocked" | "waiting" | "closed" };
export function useFrontier(scope: { project: string; workspace: string } | undefined, parent: string | null, enabled: boolean, revision: unknown) {
  const [value, setValue] = useState<{ key: string; rows: Record<string, FrontierItem> } | null>(null);
  const [error, setError] = useState("");
  const key = JSON.stringify([scope?.project, scope?.workspace, parent]);
  useEffect(() => {
    if (!enabled || !scope) return;
    const params = new URLSearchParams({ ...scope, nodeId: parent ?? "" });
    return watchQuery<Record<FrontierItem["status"], FrontierRow[]>>("/api/desktop-v3/frontier?" + params, 15000, result => {
      const rows: Record<string, FrontierItem> = {};
      for (const status of ["frontier", "claimed", "blocked", "waiting", "closed"] as const) {
        for (const row of result[status]) rows[row.id] = { ...row, status };
      }
      setValue({ key, rows }); setError("");
    }, e => { setValue(null); setError(String(e)); });
  }, [key, enabled, revision]);
  return { rows: enabled && value?.key === key ? value.rows : undefined, error: enabled ? error : "" };
}
