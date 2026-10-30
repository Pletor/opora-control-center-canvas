// Data pohledu „Požadavky a plán“: `GET /api/intake` sdíleným pollerem jednou za 30 s (vstupy a milníky se mění
// tempem srdce, ne vteřin) a `reload()` hned po rozhodnutí člověka. Chyba čtení nechá poslední známý stav a vrátí
// českou větu; data jiného projektu nebo prostoru se nikdy neukážou.
import { useCallback, useState } from "react";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { readIntake } from "./intake-api";
import type { IntakeResponse } from "./intake-plan";

const POLL_MS = 30_000;
type Read = { scope: string; data: IntakeResponse | null; error: string | null };

export function useIntakePlan(project: string, workspace: string) {
  const scope = `${project}\n${workspace}`;
  const [read, setRead] = useState<Read | null>(null);
  const [tick, setTick] = useState(0);
  usePolling(async () => {
    try {
      const data = await readIntake(project, workspace);
      setRead({ scope, data, error: null });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Požadavky a plán se nepodařilo načíst.";
      setRead(previous => ({ scope, data: previous?.scope === scope ? previous.data : null, error: message }));
    }
  }, { intervalMs: POLL_MS, refreshKeys: [project, workspace, tick] });
  const reload = useCallback(() => setTick(value => value + 1), []);
  const current = read?.scope === scope ? read : null;
  return { data: current?.data ?? null, error: current?.error ?? null, reload };
}
