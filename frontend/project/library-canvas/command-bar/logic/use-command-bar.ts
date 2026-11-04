// Příkazový řádek jako celek: otevření klávesou, odeslání zprávy srdci s kontextem plátna a čekání na jeho draft.
// Čekání = polling verzí plátna (`reload` rodiče) po ~3 s, nejdéle ~3 min; jakmile v plátně přibude nebo se změní draft,
// ohlásí se `onWrote` a lišta zmizí. Zrušit jen schová lištu, na serveru nic neruší.
import { useCallback, useEffect, useRef, useState } from "react";
import type { FlowVersion } from "@/shared/flow-editor/logic/flow-types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { sendHeartMessage } from "@/layout/heart-channel/logic/heart-api";
import { flowContext, heartWrote, LIMIT_MS, opensCommandBar, POLL_MS, snapshotOf } from "./command-bar";

export type DrawingPhase = "idle" | "waiting" | "timeout";
type Input = { project: string; workspace: string; flowId: string; viewing: FlowVersion | null; nodeIds: readonly string[]; versions: readonly FlowVersion[];
  reload: () => void; onWrote: (draft: FlowVersion) => void };

export function useCommandBar({ project, workspace, flowId, viewing, nodeIds, versions, reload, onWrote }: Input) {
  const [open, setOpen] = useState(false), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const [wait, setWait] = useState<{ known: ReadonlyMap<string, string>; started: number; timedOut: boolean } | null>(null);
  const wrote = useRef(onWrote);
  wrote.current = onWrote;

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (opensCommandBar({ key: event.key, ctrlKey: event.ctrlKey, metaKey: event.metaKey, altKey: event.altKey, target: event.target as HTMLElement | null })) { event.preventDefault(); setOpen(true); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Načítání verzí jde přes sdílený poller (pauza po dotazu, ve skryté záložce stojí); vteřiny odpočtu tikají hodinami.
  const [now, setNow] = useState(Date.now());
  const waiting = !!wait && !wait.timedOut;
  usePolling(() => { reload(); return Promise.resolve(); }, { intervalMs: POLL_MS, enabled: waiting, immediate: false });
  useEffect(() => {
    if (!waiting) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [waiting]);
  const seconds = wait ? Math.floor((now - wait.started) / 1000) : 0;
  useEffect(() => { if (waiting && seconds * 1000 >= LIMIT_MS) setWait((old) => old && { ...old, timedOut: true }); }, [waiting, seconds]);

  useEffect(() => {
    if (!wait) return;
    const draft = heartWrote(wait.known, versions);
    if (draft) { setWait(null); wrote.current(draft); }
  }, [wait, versions]);

  const send = useCallback(async (text: string) => {
    setBusy(true);
    try {
      const known = snapshotOf(versions);
      await sendHeartMessage(project, workspace, text, flowContext(flowId, viewing?.id ?? null, nodeIds));
      setError(""); setOpen(false); setNow(Date.now()); setWait({ known, started: Date.now(), timedOut: false });
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); } finally { setBusy(false); }
  }, [project, workspace, flowId, viewing, nodeIds, versions]);

  const phase: DrawingPhase = !wait ? "idle" : wait.timedOut ? "timeout" : "waiting";
  return { open, setOpen, error, busy, send, phase, seconds: Math.max(0, seconds), cancel: () => setWait(null) };
}
