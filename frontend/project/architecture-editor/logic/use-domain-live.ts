// Jediné místo, které načítá živý stav domén (docs/domeny-a-worktree.md §10): stav práce worktree
// a stav webu. Jen přes sdílený `usePolling`: stav práce 10 s v detailu domény a 30 s na přehledu,
// web 60 s (backend drží cache 60 s) a ruční obnovení. Po chybě zůstanou poslední data, kolo se
// odsune 10 → 20 → 60 s a ve skryté záložce poller stojí. Dílky data dostanou od ArchitectureEditor.
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { normalizeWorkStatus, type WorkStatus } from "../live-status/logic/live-model";
import { emptySlot, liveDelay, slotFailed, slotLoaded, slotLoading, WEB_INTERVAL_MS, WORK_INTERVAL_MS, type LiveSlot } from "../live-status/logic/live-poll";
import { stateChanges } from "../live-status/logic/session-state";
import { mergeHosts, normalizeWebStatus, type WebHost } from "../live-status/logic/web-status";

export type DomainLive = {
  /** Stav worktree se čte jen u projektů, které worktree mají (schopnost `worktreeLive`). */
  worktreeLive: boolean;
  work: LiveSlot<WorkStatus>;
  web: LiveSlot<WebHost[]>;
  /** Věta pro `aria-live`: jen změny stavu worktree od minulého čtení. */
  announcement: string;
  refreshWeb: () => void;
};

const messageOf = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

export function useDomainLive(project: string, domainId: string | null, worktreeLive: boolean): DomainLive {
  const [work, setWork] = useState(() => emptySlot<WorkStatus>());
  const [web, setWeb] = useState(() => emptySlot<WebHost[]>());
  const [announcement, setAnnouncement] = useState("");
  const scope = useRef({ project, domainId });
  useEffect(() => { scope.current = { project, domainId }; });
  const failures = useRef({ work: 0, web: 0 });
  const lastWork = useRef<WorkStatus | null>(null);
  const forceWeb = useRef(false);
  const workBase = domainId ? WORK_INTERVAL_MS.detail : WORK_INTERVAL_MS.landing;
  const base = useRef(workBase);
  useEffect(() => { base.current = workBase; });

  usePolling(async () => {
    const asked = scope.current;
    setWork(slotLoading);
    try {
      const next = normalizeWorkStatus(await api<unknown>("/api/project-architecture/work-status?" + new URLSearchParams({ project: asked.project })));
      if (scope.current.project !== asked.project) return;
      setAnnouncement(stateChanges(lastWork.current, next, scope.current.domainId ?? undefined));
      lastWork.current = next;
      failures.current.work = 0;
      setWork((slot) => slotLoaded(slot, next, Date.now()));
    } catch (cause) {
      failures.current.work += 1;
      setWork((slot) => slotFailed(slot, messageOf(cause)));
    }
  }, { intervalMs: () => liveDelay(base.current, failures.current.work), enabled: worktreeLive && !!project, refreshKeys: [project, !!domainId] });

  const webPoll = usePolling(async () => {
    const asked = scope.current;
    const params = new URLSearchParams({ project: asked.project });
    if (asked.domainId) params.set("domain", asked.domainId);
    if (forceWeb.current) { params.set("refresh", "1"); forceWeb.current = false; }
    setWeb(slotLoading);
    try {
      const hosts = normalizeWebStatus(await api<unknown>("/api/project-architecture/web-status?" + params));
      if (scope.current.project !== asked.project) return;
      failures.current.web = 0;
      setWeb((slot) => slotLoaded(slot, mergeHosts(slot.data ?? [], hosts), Date.now()));
    } catch (cause) {
      failures.current.web += 1;
      setWeb((slot) => slotFailed(slot, messageOf(cause)));
    }
  }, { intervalMs: () => liveDelay(WEB_INTERVAL_MS, failures.current.web), enabled: !!project, refreshKeys: [project, domainId] });

  const refreshWeb = useCallback(() => { forceWeb.current = true; void webPoll.refresh(); }, [webPoll]);
  return { worktreeLive, work, web, announcement, refreshWeb };
}
