import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { createPoller } from "@/shared/hooks/logic/poller";
import { FormalReads, type FormalRecord } from "./formal-verification";
import { readFormalDetail, readFormalHistory } from "./formal-verification-read";

const message = (error: unknown) => error instanceof Error ? error.message : "Formální podklady nejsou dostupné.";
export function useFormalVerification(project: string, workspace: string, enabled: boolean, refreshRevision: number) {
  const scopeKey = JSON.stringify([project, workspace]);
  const [selection, setSelection] = useState({ scopeKey, id: "" }), [attempt, setAttempt] = useState(0);
  const selectedId = selection.scopeKey === scopeKey ? selection.id : "";
  const key = JSON.stringify([scopeKey, enabled, refreshRevision, attempt]);
  const detailKey = JSON.stringify([key, selectedId]);
  const lists = useRef(new FormalReads()), details = useRef(new FormalReads());
  lists.current.context(key); details.current.context(detailKey);
  const [state, setState] = useState({ key, requests: [] as FormalRecord[], busy: false, error: "" });
  const [detail, setDetail] = useState({ key: detailKey, record: null as FormalRecord | null, busy: false, error: "" });
  const shown = state.key === key ? state : { key, requests: [], busy: enabled, error: "" };
  const shownDetail = detail.key === detailKey ? detail : { key: detailKey, record: null, busy: enabled && !!selectedId, error: "" };
  useEffect(() => {
    if (!enabled) { setState({ key, requests: [], busy: false, error: "" }); return; }
    const poller = createPoller({ intervalMs: 15000, run: async () => {
      const valid = lists.current.next();
      setState(previous => ({ key, requests: previous.key === key ? previous.requests : [], busy: true, error: "" }));
      try {
        const requests = await readFormalHistory(api, { project, workspace });
        if (valid()) setState({ key, requests, busy: false, error: "" });
      } catch (error) { if (valid()) setState({ key, requests: [], busy: false, error: message(error) }); }
    } });
    poller.start();
    return () => { lists.current.invalidate(); poller.stop(); };
  }, [key, project, workspace, enabled]);
  useEffect(() => {
    if (!enabled || !selectedId) { setDetail({ key: detailKey, record: null, busy: false, error: "" }); return; }
    const poller = createPoller({ intervalMs: 15000, run: async () => {
      const valid = details.current.next();
      setDetail(previous => ({ key: detailKey, record: previous.key === detailKey ? previous.record : null, busy: true, error: "" }));
      try {
        const record = await readFormalDetail(api, { project, workspace }, selectedId);
        if (valid()) setDetail({ key: detailKey, record, busy: false, error: "" });
      } catch (error) { if (valid()) setDetail({ key: detailKey, record: null, busy: false, error: message(error) }); }
    } });
    poller.start();
    return () => { details.current.invalidate(); poller.stop(); };
  }, [detailKey, selectedId, project, workspace, enabled]);
  return { project, workspace, requests: shown.requests, busy: shown.busy, error: shown.error, selectedId,
    selected: shownDetail.record, detailBusy: shownDetail.busy, detailError: shownDetail.error,
    missingSelection: !!selectedId && !shownDetail.busy && !shownDetail.error && !shownDetail.record,
    select: (id: string) => { if (id === selectedId) return; details.current.invalidate(); setSelection({ scopeKey, id }); },
    refresh: () => { lists.current.invalidate(); details.current.invalidate(); setAttempt(value => value + 1); } };
}
export type FormalVerificationView = ReturnType<typeof useFormalVerification>;
