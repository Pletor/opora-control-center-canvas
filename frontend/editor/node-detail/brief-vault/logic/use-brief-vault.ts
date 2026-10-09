// Načtení schránky zadání: celý strom prostoru (všechny rozsahy) ze sdíleného zdroje `brief-vault-store`
// (jeden dotaz a jeden poller pro celé UI) a detail jednoho fragmentu. `revision` = otisk stavu plátna:
// jeho změna požádá o obnovu, požadavky všech panelů ze stejné změny se slijí do jednoho dotazu.
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { api } from "@/shared/types/logic/types";
import type { FragmentDetail, VaultTree } from "./brief-vault-model";
import { createVaultStore, type VaultSnapshot } from "./brief-vault-store";

export const vaultStore = createVaultStore({
  fetchTree: (project, workspace) => api<VaultTree>("/api/brief-vault?" + new URLSearchParams({ project, workspace })),
});

const EMPTY: VaultSnapshot = { error: "" };

export function useBriefVault(scope: { project: string; workspace: string } | undefined, revision: unknown) {
  const project = scope?.project ?? "";
  const workspace = scope?.workspace ?? "";
  const live = !!project && !!workspace;
  const cache = useRef<VaultSnapshot>(EMPTY);
  const subscribe = useCallback((listener: () => void) => (live ? vaultStore.subscribe(project, workspace, listener) : () => {}),
    [live, project, workspace]);
  const read = () => {
    const next = live ? vaultStore.snapshot(project, workspace) : EMPTY;
    // Stejná data = stejný objekt, jinak by React překresloval donekonečna.
    if (next.tree !== cache.current.tree || next.error !== cache.current.error) cache.current = next;
    return cache.current;
  };
  const snapshot = useSyncExternalStore(subscribe, read, read);
  const seen = useRef(revision);
  useEffect(() => {
    if (!live || Object.is(seen.current, revision)) return;
    seen.current = revision;
    vaultStore.refresh(project, workspace);
  }, [live, project, workspace, revision]);
  return { tree: snapshot.tree, error: snapshot.error };
}

/** Po vlastním zápisu do schránky: hned načíst strom pro všechny panely. */
export function reloadBriefVault(project: string, workspace: string) {
  return vaultStore.reload(project, workspace);
}

export function useFragmentDetail(project: string, workspace: string, id: string | null, revision: number | null, refresh: unknown) {
  const [value, setValue] = useState<{ key: string; detail: FragmentDetail } | null>(null);
  const [error, setError] = useState("");
  const key = JSON.stringify([project, workspace, id, revision]);
  useEffect(() => {
    if (!id) return;
    let live = true;
    const params = new URLSearchParams({ project, workspace, id });
    if (revision != null) params.set("revision", String(revision));
    setError("");
    api<FragmentDetail>("/api/brief-vault/fragment?" + params)
      .then((detail) => { if (live) setValue({ key, detail }); })
      .catch((e) => { if (live) setError(String(e)); });
    return () => { live = false; };
  }, [key, refresh]);
  return { detail: id && value?.key === key ? value.detail : undefined, error: id ? error : "" };
}

export type { VaultTree };
