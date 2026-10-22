import { useState } from "react";
import { api } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { parseProcessHealth, type ProcessHealth } from "./source-health";

/** Zdraví zdrojů po 15 s přes sdílený poller (ve skryté záložce stojí); jen dokud je pohled otevřený. */
export function useProcessHealth(project: string, workspace: string) {
  const key = JSON.stringify([project, workspace]);
  const [value, setValue] = useState<{ key: string; health: ProcessHealth | null; error: string } | null>(null);
  usePolling(async () => {
    try {
      const raw = await api<unknown>("/api/oporahub/process-health?" + new URLSearchParams({ project, workspace }));
      setValue({ key, health: parseProcessHealth(raw), error: "" });
    } catch (error) { setValue({ key, health: null, error: error instanceof Error ? error.message : String(error) }); }
  }, { intervalMs: 15000, enabled: !!project && !!workspace, refreshKeys: [key] });
  return value?.key === key ? value : { key, health: null, error: "" };
}
