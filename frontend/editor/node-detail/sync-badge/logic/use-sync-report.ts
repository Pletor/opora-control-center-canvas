// Načte echo a verdikt Oracle pro otevřený projekt. Jediné místo, kde dílek sahá na síť;
// samotný štítek dostává hotová data v props. Report se drží v paměti okna, přepočet si
// vyžádá `refresh()` — aplikace nic nespouští sama a na pozadí nic nepolluje.
//
// `GET /api/sync-report` trvá na živých projektech 3–6 s, a report přitom čte jen dashboard
// procesu v detailu OporaHubu. Proto se načítá jen při `enabled` (otevřený detail OporaHubu):
// editor ani přehled OporaHubu na něj nečekají. Zavřením detailu report nezmizí; při dalším
// otevření se znovu načte jen tehdy, když se mezitím změnil projekt, prostor nebo přišel `refresh()`.
import { useCallback, useEffect, useRef, useState } from "react";

import { fetchSyncReport } from "@/shared/desktop-state/logic/api";
import type { SyncReport } from "@/shared/desktop-state/logic/types";

export type SyncReportState = {
  report: SyncReport | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
};

/** Klíč jednoho načtení: projekt, prostor a pořadí vyžádaného přepočtu. */
export function syncReportKey(project: string, workspace: string, attempt: number): string {
  return JSON.stringify([project, workspace, attempt]);
}

/**
 * Má se teď sahat na síť? Jen se zapnutým čtením, známým projektem i prostorem a když poslední
 * úspěšné načtení (`lastKey`) patřilo k jinému klíči. Opakované otevření detailu bez změny nic nenačte.
 */
export function shouldFetchSyncReport(enabled: boolean, project: string, workspace: string, attempt: number, lastKey: string | null): boolean {
  if (!enabled || !project || !workspace) return false;
  return lastKey !== syncReportKey(project, workspace, attempt);
}

export function useSyncReport(project: string, workspace: string, enabled = true): SyncReportState {
  const [report, setReport] = useState<SyncReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const lastKey = useRef<string | null>(null);

  // Jiný projekt nebo prostor: starý report neplatí, ani když se zrovna nenačítá.
  // Efekt stojí před načítacím, takže při změně scope proběhne dřív a načtení pak vidí prázdný klíč.
  useEffect(() => {
    lastKey.current = null;
    setReport(null);
    setError(null);
  }, [project, workspace]);

  useEffect(() => {
    if (!shouldFetchSyncReport(enabled, project, workspace, attempt, lastKey.current)) return;
    const key = syncReportKey(project, workspace, attempt);
    let live = true;
    setLoading(true);
    fetchSyncReport(project, workspace)
      .then((next) => {
        if (!live) return;
        lastKey.current = key;
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
