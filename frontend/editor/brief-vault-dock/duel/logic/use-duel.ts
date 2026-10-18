// Čtení duelu pro sekci Duel: otevřený duel se načítá živě sdíleným pollerem (`createPoller`, každé 3 s, ve skryté
// záložce stojí). Vlastní zápis se promítne hned z odpovědi serveru (`apply`), bez čekání na další kolo; starší
// odpověď pollu (nižší revize fragmentu duelu) novější stav nepřepíše. Představa se načte při změně stromu.
import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { createPoller, type Poller } from "@/shared/hooks/logic/poller";
import { useVaultGet, type VaultScope } from "../../logic/vault-actions";
import { applyWrite, type DuelResponse, type DuelWrite, type VisionResponse } from "./duel-view";

export const DUEL_POLL_MS = 3000;

export function duelUrl(scope: VaultScope, id: string) {
  return "/api/brief-vault/duel?" + new URLSearchParams({ ...scope, id });
}

export function visionUrl(scope: VaultScope, scopeNodeId: string) {
  return "/api/brief-vault/vision?" + new URLSearchParams({ ...scope, scopeNodeId });
}

type Held = { id: string; data: DuelResponse } | null;

/** Novější stav vyhrává: odpověď s nižší revizí fragmentu duelu se zahodí. */
function newer(current: Held, id: string, data: DuelResponse): Held {
  if (current?.id === id && (current.data.duel.fragment.revision ?? 0) > (data.duel.fragment.revision ?? 0)) return current;
  return { id, data };
}

/** Živý duel: `apply` promítne odpověď zápisu hned, `refresh` načte znovu (běžící dotaz se nezdvojí). */
export function useDuel(scope: VaultScope, id: string | null) {
  const [value, setValue] = useState<Held>(null);
  const [error, setError] = useState("");
  const poller = useRef<Poller | null>(null);
  useEffect(() => {
    if (!id) return;
    let live = true;
    setError("");
    const url = duelUrl(scope, id);
    const next = createPoller({
      run: () => api<DuelResponse>(url).then((data) => { if (live) { setValue((current) => newer(current, id, data)); setError(""); } })
        .catch((e) => { if (live) setError(e instanceof Error ? e.message : String(e)); }),
      intervalMs: DUEL_POLL_MS,
    });
    poller.current = next;
    next.start();
    return () => { live = false; next.stop(); if (poller.current === next) poller.current = null; };
  }, [scope, id]);
  const apply = (write: DuelWrite) => setValue((current) => (current && current.id === id ? { id: current.id, data: applyWrite(current.data, write) } : current));
  return { data: id && value?.id === id ? value.data : undefined, error: id ? error : "", apply, refresh: () => poller.current?.refresh() };
}

export function useVision(scope: VaultScope, scopeNodeId: string, refresh: unknown) {
  return useVaultGet<VisionResponse>(visionUrl(scope, scopeNodeId), refresh);
}
