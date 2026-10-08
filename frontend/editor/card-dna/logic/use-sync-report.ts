import { useEffect, useState } from "react";
import type { SyncReport } from "@/shared/desktop-state/logic/types";
import { fetchSyncReport } from "@/shared/desktop-state/logic/api";
/** Načítá jen aktivní záložka Kód; odpověď opuštěného scope se už nepřipojí. */
export function useSyncReport(project: string, workspace: string) {
  const [report, setReport] = useState<SyncReport | null>(null); const [error, setError] = useState("");
  useEffect(() => {
    let alive = true; setReport(null); setError("");
    fetchSyncReport(project, workspace).then(value => { if (alive) setReport(value); }).catch(reason => { if (alive) setError(String(reason)); });
    return () => { alive = false; };
  }, [project, workspace]);
  return { report, error };
}
