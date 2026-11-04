// Příkazový řádek jako celek: otevření klávesou, odeslání zprávy srdci s kontextem plátna a čekání na jeho draft.
// Čekání se řídí dávkou srdce, ne pevným limitem: každé ~2 s se ptá na stav srdce (`fetchHeartStatus`) a na verze plátna
// (`reload` rodiče). Draft v plátně = hotovo (`onWrote`); dávka s naším zadáním, která skončila bez draftu, je odpověď
// bez kreslení nebo chyba (okno „Co srdce dělá“ se samo otevře). Zrušit jen schová lištu, na serveru nic neruší.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FlowVersion } from "@/shared/flow-editor/logic/flow-types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { fetchHeartStatus, sendHeartMessage, type HeartStatus } from "@/layout/heart-channel/logic/heart-api";
import { flowContext, heartWrote, opensCommandBar, snapshotOf } from "./command-bar";
import { barText, isActive, opensDetail, ownedWork, workPhase, type WorkPhase } from "./heart-work";

export type DrawingPhase = "idle" | WorkPhase;
const POLL_MS = 2000;
type Input = { project: string; workspace: string; flowId: string; viewing: FlowVersion | null; nodeIds: readonly string[]; versions: readonly FlowVersion[];
  reload: () => void; onWrote: (draft: FlowVersion) => void };
type Wait = { known: ReadonlyMap<string, string>; sentAt: number; text: string; status: HeartStatus | null; finishedSeenAt: number | null };

export function useCommandBar({ project, workspace, flowId, viewing, nodeIds, versions, reload, onWrote }: Input) {
  const [open, setOpenState] = useState(false), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const [wait, setWait] = useState<Wait | null>(null), [detail, setDetail] = useState(false), [draft, setDraft] = useState("");
  const wrote = useRef(onWrote);
  wrote.current = onWrote;
  const setOpen = useCallback((value: boolean) => { setOpenState(value); if (!value) setDraft(""); }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (opensCommandBar({ key: event.key, ctrlKey: event.ctrlKey, metaKey: event.metaKey, altKey: event.altKey, target: event.target as HTMLElement | null })) { event.preventDefault(); setOpenState(true); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const [now, setNow] = useState(Date.now());
  const work = useMemo(() => wait && ownedWork(wait.status, flowId, wait.sentAt), [wait, flowId]);
  const phase: DrawingPhase = !wait ? "idle" : workPhase({ work, status: wait.status, sentAt: wait.sentAt, now, finishedSeenAt: wait.finishedSeenAt });
  const active = phase !== "idle" && isActive(phase);

  // Dotazy na srdce a verze jdou přes sdílený poller (pauza po dotazu, ve skryté záložce stojí); vteřiny tikají hodinami.
  usePolling(async () => {
    reload();
    const status = await fetchHeartStatus(project, workspace).catch(() => null);
    if (status) setWait((old) => old && { ...old, status });
  }, { intervalMs: POLL_MS, enabled: active, immediate: false });
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [active]);

  // Skončenou dávku vidíme poprvé teď; draft může do plátna dorazit o chvíli později, proto ještě chvíli počkáme.
  useEffect(() => {
    if (wait && work && !work.running && wait.finishedSeenAt === null) { setNow(Date.now()); setWait({ ...wait, finishedSeenAt: Date.now() }); }
  }, [wait, work]);
  useEffect(() => { if (phase !== "idle" && opensDetail(phase)) setDetail(true); }, [phase]);

  useEffect(() => {
    if (!wait) return;
    const written = heartWrote(wait.known, versions);
    if (written) { setWait(null); setDetail(false); wrote.current(written); }
  }, [wait, versions]);

  const send = useCallback(async (text: string) => {
    setBusy(true);
    try {
      const known = snapshotOf(versions);
      await sendHeartMessage(project, workspace, text, flowContext(flowId, viewing?.id ?? null, nodeIds));
      setError(""); setOpenState(false); setDraft(""); setDetail(false); setNow(Date.now());
      setWait({ known, sentAt: Date.now(), text, status: null, finishedSeenAt: null });
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); } finally { setBusy(false); }
  }, [project, workspace, flowId, viewing, nodeIds, versions]);

  const elapsedMs = !wait ? 0 : work && !work.running && work.durationMs !== null ? work.durationMs : Math.max(0, now - wait.sentAt);
  const cancel = () => { setWait(null); setDetail(false); };
  /** Vrátí text zadání do pole (příkazový řádek, na prázdném plátně výzva) a lištu zavře. */
  const retry = () => { if (wait) { setDraft(wait.text); setOpenState(true); } cancel(); };
  const text = phase === "idle" ? "" : barText(phase, work, elapsedMs, wait?.status?.typicalMs);
  return { open, setOpen, error, busy, send, phase, text, work, elapsedMs, typicalMs: wait?.status?.typicalMs ?? null, detail, setDetail, draft, cancel, retry };
}
