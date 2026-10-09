import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
export type CardLease = { owner: string; expiresAt: number; active: boolean; serverOffset: number };
export function useLeases(project: string, workspace: string) {
  const [value, setValue] = useState<{ key: string; nodes: Record<string, CardLease> } | null>(null);
  const key = JSON.stringify([project, workspace]);
  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const result = await api<{ serverNow: number; nodes: Record<string, Omit<CardLease, "serverOffset">> }>("/api/desktop-v3/leases?" + new URLSearchParams({ project, workspace }));
        const serverOffset = result.serverNow - Date.now() / 1000;
        if (live) setValue({ key, nodes: Object.fromEntries(Object.entries(result.nodes).map(([id, lease]) => [id, { ...lease, serverOffset }])) });
      } catch { if (live) setValue(null); }
      if (live) timer = setTimeout(refresh, 10000);
    }
    void refresh();
    return () => { live = false; clearTimeout(timer); };
  }, [project, workspace, key]);
  return value?.key === key ? value.nodes : undefined;
}
