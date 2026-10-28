// Stav strážců projektu pro řádek Velínu: `GET /api/strazci?project=` sdíleným pollerem jednou za 30 s (strážci sami
// běží po 30–300 s, častější čtení by nic nového neřeklo). Chyba čtení nechá poslední známý stav; neplatná odpověď = null.
import { useState } from "react";
import { api } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { parseGuardStatus, type GuardStatus } from "./velin-guards";

const POLL_MS = 30_000;

export function useGuardStatus(project: string): GuardStatus | null {
  const [status, setStatus] = useState<{ project: string; value: GuardStatus | null } | null>(null);
  usePolling(async () => {
    try {
      const raw = await api<unknown>(`/api/strazci?project=${encodeURIComponent(project)}`);
      setStatus({ project, value: parseGuardStatus(raw) });
    } catch { /* poslední známý stav zůstává */ }
  }, { intervalMs: POLL_MS, refreshKeys: [project] });
  return status?.project === project ? status.value : null;
}
