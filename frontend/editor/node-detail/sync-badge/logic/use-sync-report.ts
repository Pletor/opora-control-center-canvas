// Načte echo a verdikt Oracle pro otevřený projekt. Jediné místo, kde dílek sahá na síť;
// samotný štítek dostává hotová data v props. Report se drží v paměti okna, přepočet si
// vyžádá `refresh()` — aplikace nic nespouští sama a na pozadí nic nepolluje.
import { useCallback, useEffect, useState } from "react";

import { fetchSyncReport } from "@/shared/desktop-state/logic/api";
import type { SyncReport } from "@/shared/desktop-state/logic/types";

export type SyncReportState = {
  report: SyncReport | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
};

export function useSyncReport(project: string, workspace: string, enabled = true): SyncReportState {
  const [report, setReport] = useState<SyncReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!enabled || !project || !workspace) {
      setReport(null);
      return;
    }
    let live = true;
    setLoading(true);
    fetchSyncReport(project, workspace)
      .then((next) => {
        if (!live) return;
        setReport(next);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (!live) return;
        setReport(null);
        setError(reason instanceof Error ? reason.message : "Echo se nepodařilo načíst.");
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [project, workspace, enabled, attempt]);

  const refresh = useCallback(() => setAttempt((value) => value + 1), []);
  return { report, loading, error, refresh };
}
