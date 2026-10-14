import { useState } from "react";
import { api } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { keepSame } from "@/shared/hooks/logic/same-response";
export type CardLease = { owner: string; expiresAt: number; active: boolean; serverOffset: number };
/** Stejné pronájmy (bez posunu hodin) a posun do 2 s od starého: nová data nic nemění. */
export function leasesUnchanged(before: Record<string, CardLease>, after: Record<string, CardLease>) {
  const ids = Object.keys(after);
  if (ids.length !== Object.keys(before).length) return false;
  return ids.every((id) => {
    const old = before[id]; const next = after[id];
    return !!old && old.owner === next.owner && old.expiresAt === next.expiresAt && old.active === next.active && Math.abs(old.serverOffset - next.serverOffset) < 2;
  });
}
export function useLeases(project: string, workspace: string) {
  const [value, setValue] = useState<{ key: string; nodes: Record<string, CardLease> } | null>(null);
  const key = JSON.stringify([project, workspace]);
  usePolling(async () => {
    try {
      const result = await api<{ serverNow: number; nodes: Record<string, Omit<CardLease, "serverOffset">> }>("/api/desktop-v3/leases?" + new URLSearchParams({ project, workspace }));
      const serverOffset = result.serverNow - Date.now() / 1000;
      const nodes = Object.fromEntries(Object.entries(result.nodes).map(([id, lease]) => [id, { ...lease, serverOffset }]));
      // Posun hodin se mění o zlomky sekundy při každém dotazu; bez změny pronájmů zůstane stará reference.
      setValue((current) => (current?.key === key && leasesUnchanged(current.nodes, nodes) ? current : { key, nodes }));
    } catch { setValue((current) => (current?.key === key ? null : current)); }
  }, { intervalMs: 10000, refreshKeys: [key] });
  return value?.key === key ? value.nodes : undefined;
}
