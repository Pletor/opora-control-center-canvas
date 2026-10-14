// Vazba přepínače disciplín na React: drží poslední volbu (nebo `null`, dokud člověk nevybral) a ukládá ji
// jednou pro aplikaci pod `opora:vault-discipline:v1` (při prvním čtení převezme starou volbu stopy).
// Seznam disciplín s počty živých fragmentů čte z `GET /api/brief-vault/disciplines`. Pravidla jsou v `disciplines.ts`.
import { useCallback, useState } from "react";
import { readDiscipline, writeDiscipline, type DisciplineView, type ServerDiscipline } from "./disciplines";
import { useVaultGet, type VaultScope } from "./vault-actions";

export function useVaultDiscipline(): [DisciplineView | null, (view: DisciplineView) => void] {
  const [view, setView] = useState<DisciplineView | null>(readDiscipline);
  const choose = useCallback((next: DisciplineView) => { setView(next); writeDiscipline(next); }, []);
  return [view, choose];
}

/** Tabulka disciplín s počty živých fragmentů prostoru; `refresh` = nový strom (po zápisu). */
export function useServerDisciplines(scope: VaultScope, refresh: unknown): ServerDiscipline[] | undefined {
  const url = scope.project && scope.workspace ? "/api/brief-vault/disciplines?" + new URLSearchParams(scope) : null;
  return useVaultGet<{ disciplines: ServerDiscipline[]; unassigned: number }>(url, refresh).data?.disciplines;
}
