// Jediné čtení kontroly mapy přes worktree (docs/navrhy/2026-10-28-kontrola-mapy-a-worktree.md §3, §5) pro Studio,
// Editor architektury (stav karet plátna 2) i Velín. Sdílený poller po 30 s jako stav strážců: worktree mění agenti, ne člověk
// v tomto okně, a backend drží cache podle otisku pohledu; `refreshKey` (otisk mapy mainu) čte hned po uložení mapy.
// Jen projekty s worktree (`enabled` = schopnost `worktreeLive`). Chyba nebo chybějící endpoint (404) nechá poslední
// známý stav, na začátku null = žádné worktree; nic se nerozbije. Stejná odpověď vrátí týž objekt (`overlayKey`).
import { useState } from "react";
import { api } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { mapWorktreesUrl, normalizeWorktreeOverlay, overlayKey, type MapWorktreeOverlay } from "../domain-site/map-check/logic/map-check-worktrees";

const POLL_MS = 30_000;

type Held = { project: string; key: string; value: MapWorktreeOverlay | null };

export function useMapWorktrees(project: string, enabled: boolean, refreshKey?: string): MapWorktreeOverlay | null {
  const [held, setHeld] = useState<Held | null>(null);
  usePolling(async () => {
    try {
      const value = normalizeWorktreeOverlay(await api<unknown>(mapWorktreesUrl(project)));
      const key = overlayKey(value);
      setHeld((prior) => (prior?.project === project && prior.key === key ? prior : { project, key, value: key ? value : null }));
    } catch { /* poslední známý stav zůstává; 404 = starší server bez worktree */ }
  }, { intervalMs: POLL_MS, enabled: enabled && !!project, refreshKeys: [project, refreshKey] });
  return enabled && held?.project === project ? held.value : null;
}
