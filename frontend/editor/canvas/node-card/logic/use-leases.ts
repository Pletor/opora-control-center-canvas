import { useState } from "react";
import { api } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
export type CardLease = { owner: string; expiresAt: number; active: boolean; serverOffset: number };
export function useLeases(project: string, workspace: string) {
  const [value, setValue] = useState<{ key: string; nodes: Record<string, CardLease> } | null>(null);
  const key = JSON.stringify([project, workspace]);
  usePolling(async () => {
    try {
      const result = await api<{ serverNow: number; nodes: Record<string, Omit<CardLease, "serverOffset">> }>("/api/desktop-v3/leases?" + new URLSearchParams({ project, workspace }));
      const serverOffset = result.serverNow - Date.now() / 1000;
      setValue({ key, nodes: Object.fromEntries(Object.entries(result.nodes).map(([id, lease]) => [id, { ...lease, serverOffset }])) });
    } catch { setValue((current) => (current?.key === key ? null : current)); }
  }, { intervalMs: 10000, refreshKeys: [key] });
  return value?.key === key ? value.nodes : undefined;
}
