import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { advanceHistory, ReconciliationRequests, ROOT, type HistoryEntry, type ReconciliationAttempt, type ReconciliationCandidate, type ReconciliationHistory } from "./reconciliation";
const message = (error: unknown) => error instanceof Error ? error.message : String(error);

export function useReconciliationCandidate(project: string, workspace: string, evidenceId: string, enabled: boolean, revisionKey: string) {
  const key = JSON.stringify([project, workspace, evidenceId, enabled, revisionKey]);
  const active = useRef(key), requests = useRef(new ReconciliationRequests());
  if (active.current !== key) { active.current = key; requests.current.invalidate(); }
  const [state, setState] = useState<{ key: string; candidate: ReconciliationCandidate | null; busy: boolean; error: string }>({ key, candidate: null, busy: false, error: "" });
  useEffect(() => {
    const valid = requests.current.next();
    if (!enabled || !evidenceId) { setState({ key, candidate: null, busy: false, error: "" }); return; }
    setState({ key, candidate: null, busy: true, error: "" });
    const query = new URLSearchParams({ project, workspace, evidenceId });
    api<ReconciliationCandidate>(`${ROOT}/candidate?${query}`).then(candidate => {
      if (valid()) setState({ key, candidate, busy: false, error: "" });
    }).catch(error => { if (valid()) setState({ key, candidate: null, busy: false, error: message(error) }); });
    return () => requests.current.invalidate();
  }, [key, project, workspace, evidenceId, enabled]);
  return state.key === key ? state : { key, candidate: null, busy: !!evidenceId && enabled, error: "" };
}

export function useReconciliationHistory(project: string, workspace: string, bindingId: string, enabled: boolean, revisionKey: string) {
  const key = JSON.stringify([project, workspace, bindingId, enabled, revisionKey]);
  const active = useRef(key), requests = useRef(new ReconciliationRequests()), loading = useRef(false);
  if (active.current !== key) { active.current = key; requests.current.invalidate(); loading.current = false; }
  const empty = { key, items: [] as HistoryEntry[], nextCursor: null as string | null, attempts: [] as ReconciliationAttempt[], nextAttemptCursor: null as string | null, busy: false, error: "" };
  const [state, setState] = useState(empty);
  const shown = state.key === key ? state : empty;
  const query = new URLSearchParams({ project, workspace });
  const url = `${ROOT}/${encodeURIComponent(bindingId)}/history?${query}`;
  useEffect(() => {
    const valid = requests.current.next();
    if (!enabled || !bindingId) { setState(empty); return; }
    loading.current = true; setState({ ...empty, busy: true });
    api<ReconciliationHistory>(url).then(page => {
      if (valid()) setState({ ...empty, items: page.items, nextCursor: page.nextCursor, attempts: page.attempts, nextAttemptCursor: page.nextAttemptCursor });
    }).catch(error => { if (valid()) setState({ ...empty, error: message(error) }); })
      .finally(() => { if (valid()) loading.current = false; });
    return () => requests.current.invalidate();
  }, [key, url, bindingId, enabled]);
  async function more() {
    if ((!shown.nextCursor && !shown.nextAttemptCursor) || loading.current || !enabled) return;
    loading.current = true; const valid = requests.current.next();
    setState({ ...shown, busy: true, error: "" });
    try {
      const cursors = new URLSearchParams({ ...(shown.nextCursor ? { cursor: shown.nextCursor } : {}), ...(shown.nextAttemptCursor ? { attemptCursor: shown.nextAttemptCursor } : {}) });
      const page = await api<ReconciliationHistory>(`${url}&${cursors}`);
      if (valid()) setState({ ...shown, ...advanceHistory(shown, page), busy: false });
    } catch (error) { if (valid()) setState({ ...shown, busy: false, error: message(error) }); }
    finally { if (valid()) loading.current = false; }
  }
  return { ...shown, more };
}
