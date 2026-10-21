import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { createPoller } from "@/shared/hooks/logic/poller";
import { trackSaveWrite } from "@/shared/hooks/logic/save-coordinator";
import { CONTENT_ROOT, contentQuery, contentDetailUrl, contentAction, contentAcknowledgement, ContentRequests,
  type ContentList, type ContentDetail, type ContentConflict } from "./content-changes";
import { parseContentList, parseContentDetail, parseContentRebase } from "./content-parse";
import { postContent } from "./content-api";

const message = (error: unknown) => error instanceof Error ? error.message : "Změny obsahu nejsou dostupné.";
export function useContentChanges(project: string, workspace: string, enabled: boolean, readOnly: boolean, revision: number, onApplied: () => void) {
  const scope = { project, workspace }, scopeKey = JSON.stringify([project, workspace]);
  const [selection, setSelection] = useState({ scopeKey, id: "" }), [attempt, setAttempt] = useState(0);
  const selectedId = selection.scopeKey === scopeKey ? selection.id : "";
  const key = JSON.stringify([scopeKey, enabled, revision, attempt]), detailKey = JSON.stringify([key, selectedId]);
  const lists = useRef(new ContentRequests()), details = useRef(new ContentRequests()), writes = useRef(new ContentRequests());
  lists.current.context(key); details.current.context(detailKey); writes.current.context(detailKey);
  const [state, setState] = useState({ key, value: null as ContentList | null, busy: false, error: "" });
  const [detail, setDetail] = useState({ key: detailKey, value: null as ContentDetail | null, busy: false, error: "" });
  const [pending, setPending] = useState(false), [ack, setAck] = useState("");
  const [feedback, setFeedback] = useState({ key: detailKey, notice: "", error: "", conflicts: [] as ContentConflict[] });
  const shown = state.key === key ? state : { key, value: null, busy: enabled, error: "" };
  const inspected = detail.key === detailKey ? detail : { key: detailKey, value: null, busy: enabled && !!selectedId, error: "" };
  const info = feedback.key === detailKey ? feedback : { notice: "", error: "", conflicts: [] };
  const acknowledgementKey = inspected.value ? `${scopeKey}:${contentAcknowledgement(inspected.value.proposal)}` : "";
  const refresh = () => { lists.current.invalidate(); details.current.invalidate(); setAck(""); setAttempt(v => v + 1); };
  useEffect(() => () => writes.current.invalidate(), []);
  useEffect(() => {
    if (!enabled) return;
    const poller = createPoller({ intervalMs: 15000, run: async () => {
      const valid = lists.current.next();
      setState(old => ({ key, value: old.key === key ? old.value : null, busy: true, error: "" }));
      try {
        await api("/api/access/ui-session");
        const value = parseContentList(await api<unknown>(`${CONTENT_ROOT}?${contentQuery(scope)}`));
        if (valid()) setState({ key, value, busy: false, error: "" });
      } catch (error) { if (valid()) setState({ key, value: null, busy: false, error: message(error) }); }
    } });
    poller.start(); return () => { lists.current.invalidate(); poller.stop(); };
  }, [key, project, workspace, enabled]);
  useEffect(() => {
    setAck("");
    if (!enabled || !selectedId) return;
    const poller = createPoller({ intervalMs: 15000, run: async () => {
      const valid = details.current.next();
      setDetail(old => ({ key: detailKey, value: old.key === detailKey ? old.value : null, busy: true, error: "" }));
      try {
        await api("/api/access/ui-session");
        const value = parseContentDetail(await api<unknown>(contentDetailUrl(scope, selectedId)), scope, selectedId);
        if (valid()) setDetail({ key: detailKey, value, busy: false, error: "" });
      } catch (error) { if (valid()) setDetail({ key: detailKey, value: null, busy: false, error: message(error) }); }
    } });
    poller.start(); return () => { details.current.invalidate(); poller.stop(); };
  }, [detailKey, selectedId, project, workspace, enabled]);
  const disabled = !enabled || readOnly || pending || shown.busy || inspected.busy || !shown.value || !inspected.value
    || !!shown.value?.readOnly || !!inspected.value?.readOnly || !!shown.error || !!inspected.error;
  async function act(action: "accept" | "rebase") {
    if (disabled || !shown.value || !inspected.value || inspected.value.proposal.id !== selectedId) return;
    const current = inspected.value, capturedId = selectedId;
    let payload: object;
    try { payload = contentAction(scope, shown.value, current, action, ack === acknowledgementKey ? contentAcknowledgement(current.proposal) : ""); }
    catch (error) { setFeedback({ key: detailKey, notice: "", error: message(error), conflicts: [] }); return; }
    const valid = writes.current.beginWrite();
    if (!valid) return;
    setPending(true); setAck(""); setFeedback({ key: detailKey, notice: "", error: "", conflicts: [] });
    try {
      const mutation = postContent(`${CONTENT_ROOT}/${capturedId}/${action}`, payload);
      const result = await (action === "accept" ? trackSaveWrite(project, workspace, mutation) : mutation);
      if (action === "accept") {
        if (!result || typeof result !== "object" || !("id" in result) || !/^[a-f0-9]{40}$/.test(String(result.id))) throw new Error("Přijetí nebylo potvrzeno platnou revizí.");
        onApplied();
      }
      if (!valid()) return;
      if (action === "rebase") {
        const rebased = parseContentRebase(result, scope);
        if (!rebased.rebased) { setFeedback({ key: detailKey, notice: "Původní návrh zůstává zachován. Konflikty nic nepřepsaly.", error: "", conflicts: rebased.conflicts }); return; }
        details.current.invalidate(); writes.current.invalidate(); setSelection({ scopeKey, id: rebased.proposal!.id });
      }
      refresh();
    } catch (error) {
      if (valid()) setFeedback({ key: detailKey, notice: "", conflicts: [], error: message(error) + " Akce se automaticky neopakuje. Obnovte podklady a zkontrolujte historii." });
    } finally { writes.current.endWrite(); setPending(false); }
  }
  return { project, workspace, list: shown.value, items: shown.value?.items ?? [], busy: shown.busy, error: shown.error,
    selectedId, detail: inspected.value, detailBusy: inspected.busy, detailError: inspected.error, disabled, pending,
    notice: info.notice, actionError: info.error, conflicts: info.conflicts,
    acknowledged: !!acknowledgementKey && ack === acknowledgementKey,
    acknowledge: (checked: boolean) => setAck(checked ? acknowledgementKey : ""),
    select: (id: string) => { if (!pending) { details.current.invalidate(); writes.current.invalidate(); setAck(""); setSelection({ scopeKey, id }); } },
    cancel: () => { details.current.invalidate(); writes.current.invalidate(); setAck(""); setSelection({ scopeKey, id: "" }); },
    refresh, accept: () => void act("accept"), rebase: () => void act("rebase") };
}
export type ContentChangesView = ReturnType<typeof useContentChanges>;
