// Detail vybraného běhu: `node_runs` pro stav na plátně a log událostí pro spodní panel. Neukončený běh se obnovuje
// každé 3 s sdíleným pollerem (`usePolling`), ukončený se načte jednou a dál stojí.
import { useEffect, useRef, useState } from "react";
import type { FlowRunDetail, LogEvent } from "@/shared/flow-editor/logic/flow-types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { loadLog, loadRun } from "./heart-api";

const OPEN = new Set(["queued", "running", "waiting"]);
const POLL_MS = 3000;

export function useRunDetail(runId: string | null): { run: FlowRunDetail | null; events: LogEvent[]; error: string } {
  const [run, setRun] = useState<FlowRunDetail | null>(null);
  const [events, setEvents] = useState<LogEvent[]>([]);
  const [error, setError] = useState("");
  const current = useRef(runId);
  useEffect(() => { current.current = runId; setRun(null); setEvents([]); setError(""); }, [runId]);
  usePolling(async () => {
    const id = runId;
    if (!id) return;
    try {
      const [detail, log] = await Promise.all([loadRun(id), loadLog(id)]);
      if (current.current !== id) return;
      setRun(detail); setEvents(log); setError("");
    } catch (reason) { if (current.current === id) setError(reason instanceof Error ? reason.message : String(reason)); }
  }, { intervalMs: () => run && !OPEN.has(run.status) ? 0 : POLL_MS, enabled: !!runId, refreshKeys: [runId] });
  return { run, events, error };
}
