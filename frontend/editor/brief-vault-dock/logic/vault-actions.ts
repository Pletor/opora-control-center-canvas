// Zápisy a doplňková čtení Schránky. Každý zápis jde přes POST /api/brief-vault (op), server hlídá
// guardy člověka (set-mvp, feedback, odpověď pro člověka) a po zápisu se obnoví sdílený strom pro všechna místa.
// Zápis se hlásí koordinátoru ukládání jako vlastní (`trackSaveWrite`): Schránka je součástí otisku uložené verze,
// takže bez toho by lišta verzí po každém zápisu ukázala „Změna mimo toto okno · načíst“.
import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { trackSaveWrite } from "@/shared/hooks/logic/save-coordinator";
import { reloadBriefVault } from "@/editor/node-detail/brief-vault/logic/use-brief-vault";

export type VaultScope = { project: string; workspace: string };

export async function vaultOp<T = Record<string, unknown>>(scope: VaultScope, body: Record<string, unknown>): Promise<T> {
  const result = await trackSaveWrite(scope.project, scope.workspace, api<T>("/api/brief-vault", { ...scope, ...body }));
  await reloadBriefVault(scope.project, scope.workspace);
  return result;
}

export type HistoryItem = { id: string; revision: number; kind: string; title: string; stage: string; mvp: string; note: string; by: string; actor: string; deleted: boolean; at: string; chars: number };

/** GET-hook s klíčem: načte znovu při změně klíče nebo `refresh`; starý výsledek jiného klíče neukáže. */
export function useVaultGet<T>(url: string | null, refresh: unknown) {
  const [value, setValue] = useState<{ url: string; data: T } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!url) return;
    let live = true;
    setError("");
    api<T>(url).then((data) => { if (live) setValue({ url, data }); }).catch((e) => { if (live) setError(String(e)); });
    return () => { live = false; };
  }, [url, refresh]);
  return { data: url && value?.url === url ? value.data : undefined, error: url ? error : "" };
}

export function historyUrl(scope: VaultScope, vaultScope: string) {
  return "/api/brief-vault/history?" + new URLSearchParams({ ...scope, scope: vaultScope });
}

export function researchBriefUrl(scope: VaultScope, fragment: string) {
  return "/api/brief-vault/research-brief?" + new URLSearchParams({ ...scope, fragment });
}
