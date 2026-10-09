// Načtení schránky zadání: celý strom prostoru (všechny rozsahy) a detail jednoho fragmentu. Jen čtení;
// zápis (research, MVP, vložení jako karty) je mimo tento dílek. Strom se obnoví při změně `revision`
// (stav plátna) a každých 15 s, aby odznak „zadání se změnilo“ přišel i po nové revizi fragmentu.
import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
import type { FragmentDetail, VaultTree } from "./brief-vault-model";

export function useBriefVault(scope: { project: string; workspace: string } | undefined, revision: unknown) {
  const [value, setValue] = useState<{ key: string; tree: VaultTree } | null>(null);
  const [error, setError] = useState("");
  const key = JSON.stringify([scope?.project, scope?.workspace]);
  useEffect(() => {
    if (!scope?.project || !scope.workspace) return;
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    const params = new URLSearchParams({ project: scope.project, workspace: scope.workspace });
    async function refresh() {
      try {
        const tree = await api<VaultTree>("/api/brief-vault?" + params);
        if (live) { setValue({ key, tree }); setError(""); }
      } catch (e) { if (live) setError(String(e)); }
      if (live) timer = setTimeout(refresh, 15000);
    }
    void refresh();
    return () => { live = false; clearTimeout(timer); };
  }, [key, revision]);
  return { tree: value?.key === key ? value.tree : undefined, error };
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
