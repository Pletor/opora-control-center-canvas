import { useEffect, useState } from "react";
import { watchQuery } from "@/shared/hooks/logic/query-poll";
export type CardLease = { owner: string; expiresAt: number; active: boolean; serverOffset: number };
export function useLeases(project: string, workspace: string) {
  const [value, setValue] = useState<{ key: string; nodes: Record<string, CardLease> } | null>(null);
  const key = JSON.stringify([project, workspace]);
  useEffect(() => {
    return watchQuery<{ serverNow: number; nodes: Record<string, Omit<CardLease, "serverOffset">> }>(
      "/api/desktop-v3/leases?" + new URLSearchParams({ project, workspace }), 10000, result => {
        const serverOffset = result.serverNow - Date.now() / 1000;
        setValue({ key, nodes: Object.fromEntries(Object.entries(result.nodes).map(([id, lease]) => [id, { ...lease, serverOffset }])) });
      }, () => setValue(null));
  }, [project, workspace, key]);
  return value?.key === key ? value.nodes : undefined;
}
