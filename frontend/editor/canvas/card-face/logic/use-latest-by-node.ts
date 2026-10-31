// Poslední změna všech karet prostoru jedním dotazem (`GET /api/activity-log/latest-by-node`). Rodič plátna
// předá `refreshKey` (snímek agent-state + otisk plátna a revize); nový dotaz jde jen při jeho změně. Stejná
// odpověď vrací stejný objekt, aby se nezměněné karty nepřestavěly. Chyba čtení nechá poslední známý stav.
import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { latestQuery, parseLatest, type LatestByNode } from "./face-change";

const EMPTY: LatestByNode = {};

export function useLatestByNode(project: string, workspace: string, refreshKey: string): LatestByNode {
  const scope = JSON.stringify([project, workspace]);
  const [latest, setLatest] = useState<{ scope: string; text: string; value: LatestByNode }>({ scope, text: "{}", value: EMPTY });
  const current = useRef(scope);
  current.current = scope;
  useEffect(() => {
    if (!project) return;
    const owner = scope;
    api<unknown>(latestQuery(project, workspace))
      .then((raw) => {
        if (current.current !== owner) return;
        const value = parseLatest(raw);
        const text = JSON.stringify(value);
        setLatest((before) => before.scope === owner && before.text === text ? before : { scope: owner, text, value });
      })
      .catch(() => {});
  }, [scope, project, workspace, refreshKey]);
  return latest.scope === scope ? latest.value : EMPTY;
}
