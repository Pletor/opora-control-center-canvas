// Automatické ukládání storyboardu: 700 ms po poslední změně platného konceptu zavolá `save` úložiště, změnu během
// běžícího ukládání uloží hned po jeho dokončení, při konfliktu čeká na Obnovit. Při odchodu z karty (unmount) a při
// zavření stránky (`pagehide`, `fetch` s `keepalive`) uloží neuložený platný koncept; varuje jen, když uložit nejde.
// Rozhodnutí dělá `storyboard-autosave.ts`, tady jsou jen časovač a posluchače.
import { useEffect, useRef } from "react";
import { api } from "@/shared/types/logic/types";
import { autosaveDelay, saveOnLeave, warnOnUnload, type SaveGate } from "./storyboard-autosave";
import { serialize, sortMoments, type Storyboard } from "./storyboard-model";
import type { useStoryboardStore } from "./use-storyboard-store";

type Store = ReturnType<typeof useStoryboardStore>;

export function useStoryboardAutosave({ project, workspace, nodeId, store, valid, readOnly }: {
  project: string;
  workspace: string;
  nodeId: string;
  store: Store;
  valid: boolean;
  readOnly: boolean;
}) {
  const { draft, dirty, status } = store;
  const gate: SaveGate = { dirty, valid, readOnly, status };
  const key = draft ? JSON.stringify(serialize(draft)) : "";
  const latest = useRef({ draft, gate, store });
  latest.current = { draft, gate, store };
  const pending = useRef(false);
  const failedKey = useRef<string | null>(null);
  const prev = useRef({ key, status });

  useEffect(() => {
    const before = prev.current;
    prev.current = { key, status };
    if (status === "saving") {
      // Člověk píše dál, zatímco se ukládá: uloží se hned, jak ukládání doběhne.
      if (before.status === "saving" && before.key !== key) pending.current = true;
      return;
    }
    const delay = autosaveDelay({ dirty, valid, readOnly, status }, pending.current, failedKey.current === key);
    if (delay === null) return;
    const timer = window.setTimeout(() => {
      pending.current = false;
      const { draft: board, store: current } = latest.current;
      if (!board) return;
      const sent = JSON.stringify(serialize(board));
      void current.save(board).then((ok) => { failedKey.current = ok ? null : sent; });
    }, delay);
    return () => window.clearTimeout(timer);
  }, [key, status, dirty, valid, readOnly]);

  useEffect(() => {
    const body = (board: Storyboard) => ({
      project, workspace, nodeId, expected_revision: latest.current.store.revisionRef.current, storyboard: serialize(sortMoments(board)),
    });
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!warnOnUnload(latest.current.gate)) return;
      event.preventDefault();
      event.returnValue = "";
    };
    // Zavření stránky: `api()` by nestihlo doběhnout, proto `fetch` s `keepalive` a stejnými hlavičkami (cookie jde sama).
    const onPageHide = () => {
      const { draft: board, gate: now } = latest.current;
      if (!board || !saveOnLeave(now)) return;
      try {
        void fetch("/api/storyboard", { method: "POST", keepalive: true, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body(board)) }).catch(() => undefined);
      } catch { /* tělo nad 64 kB keepalive nevezme; nic dalšího udělat nejde */ }
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    window.addEventListener("pagehide", onPageHide);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
      window.removeEventListener("pagehide", onPageHide);
      // Odchod z karty nebo módu (unmount editoru): stránka žije dál, takže stačí běžné `api()` bez čekání.
      const { draft: board, gate: now } = latest.current;
      if (board && saveOnLeave(now)) void api("/api/storyboard", body(board)).catch(() => undefined);
    };
  }, [project, workspace, nodeId]);
}
