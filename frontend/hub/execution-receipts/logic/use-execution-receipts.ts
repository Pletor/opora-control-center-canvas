import { useEffect, useRef, useState } from "react";
import { api, type CanvasNode } from "@/shared/types/logic/types";
import { ReceiptRequests, readExecutionHistory, readExecutionReceipts, type ExecutionContext, type ExecutionSummary, type ExecutionReceipt } from "./execution-receipts";
import { BUDGET_ROOT, BudgetIntent, postBudget } from "@/hub/execution-budgets/logic/execution-budgets";

type State = { key: string; context: ExecutionContext | null; executions: ExecutionSummary[]; canCancel: boolean; busy: boolean; error: string };
const empty = (key: string): State => ({ key, context: null, executions: [], canCancel: false, busy: false, error: "" });
const message = (error: unknown) => error instanceof Error ? error.message : String(error);

export function useExecutionReceipts(project: string, workspace: string, nodes: CanvasNode[], enabled: boolean, refreshRevision: number) {
  const choices = nodes.filter(node => node.kind === "node" || node.kind === "sector");
  const scope = JSON.stringify([project, workspace]);
  const [card, setCard] = useState({ scope, id: "" });
  const nodeId = card.scope === scope && choices.some(node => node.id === card.id) ? card.id : "";
  const [attempt, setAttempt] = useState(0);
  const key = JSON.stringify([scope, nodeId, enabled, refreshRevision, attempt]);
  const active = useRef(key);
  const requests = useRef(new ReceiptRequests());
  if (active.current !== key) { active.current = key; requests.current.invalidate(); }
  const [state, setState] = useState(() => empty(key));
  const shown = state.key === key ? state : empty(key);
  const [selection, setSelection] = useState({ key, id: "" });
  const selected = selection.key === key && selection.id ? shown.executions.find(item => item.executionId === selection.id) ?? null : shown.executions[0] ?? null;
  const missingSelection = selection.key === key && !!selection.id && !selected && !shown.busy;
  const id = selected?.executionId ?? "";
  const detailKey = JSON.stringify([key, id]);
  const detailActive = useRef(detailKey);
  const detailRequests = useRef(new ReceiptRequests());
  if (detailActive.current !== detailKey) { detailActive.current = detailKey; detailRequests.current.invalidate(); }
  const [detail, setDetail] = useState({ key: detailKey, receipts: [] as ExecutionReceipt[], busy: false, error: "" });
  const shownDetail = detail.key === detailKey ? detail : { key: detailKey, receipts: [], busy: !!id, error: "" };
  const cancelIntent = useRef(new BudgetIntent()), cancelWriting = useRef(false);
  const [cancelReview, setCancelReview] = useState<{ key: string; executionId: string; payload: { project: string; workspace: string; epoch: number; requestId: string } } | null>(null);
  const [cancelAck, setCancelAck] = useState(false), [cancelling, setCancelling] = useState(false);
  const cancellation = cancelReview?.key === detailKey ? cancelReview : null;
  const canCancel = shown.canCancel && !shown.busy && !shown.error && !cancelling && !!selected && ["running", "revoked"].includes(selected.state);
  function prepareCancel() {
    if (!canCancel || !selected) return;
    const base = { project, workspace, epoch: selected.epoch };
    const requestId = cancelIntent.current.request({ executionId: selected.executionId, ...base });
    setCancelReview({ key: detailKey, executionId: selected.executionId, payload: { ...base, requestId } }); setCancelAck(false);
  }
  async function confirmCancel() {
    if (!canCancel || !cancellation || !cancelAck || cancelWriting.current) return;
    cancelWriting.current = true; setCancelling(true); setCancelAck(false);
    const valid = requests.current.next();
    try {
      await postBudget(`${BUDGET_ROOT}/${encodeURIComponent(cancellation.executionId)}/cancel`, cancellation.payload);
      if (valid()) { setCancelReview(null); setAttempt(value => value + 1); }
    } catch (error) { if (valid()) { setCancelReview(null); setState({ ...shown, error: message(error) + " Zrušení se neopakuje automaticky. Obnovte historii." }); } }
    finally { cancelWriting.current = false; setCancelling(false); }
  }

  useEffect(() => {
    const valid = requests.current.next();
    if (!enabled) { setState(empty(key)); return; }
    setState({ ...empty(key), busy: true });
    readExecutionHistory(api, project, workspace, nodeId).then(data => {
      if (valid()) setState({ ...empty(key), ...data });
    }).catch(error => { if (valid()) setState({ ...empty(key), error: message(error) }); });
    return () => requests.current.invalidate();
  }, [key, project, workspace, nodeId, enabled]);

  useEffect(() => {
    const valid = detailRequests.current.next();
    if (!enabled || !id) { setDetail({ key: detailKey, receipts: [], busy: false, error: "" }); return; }
    setDetail({ key: detailKey, receipts: [], busy: true, error: "" });
    readExecutionReceipts(api, project, workspace, id).then(data => {
      if (valid()) setDetail({ key: detailKey, receipts: data.results, busy: false, error: "" });
    }).catch(error => { if (valid()) setDetail({ key: detailKey, receipts: [], busy: false, error: message(error) }); });
    return () => detailRequests.current.invalidate();
  }, [detailKey, id, project, workspace, enabled]);

  return { ...shown, choices, nodeId, project, workspace, selected, missingSelection, receipts: shownDetail.receipts,
    canCancel, cancellation, cancelAck, cancelling, prepareCancel, confirmCancel,
    acknowledgeCancel: setCancelAck, dismissCancel: () => { setCancelReview(null); setCancelAck(false); },
    detailBusy: shownDetail.busy, detailError: shownDetail.error,
    selectCard: (id: string) => { setCancelReview(null); setCancelAck(false); setCard({ scope, id }); },
    selectExecution: (id: string) => { setCancelReview(null); setCancelAck(false); setSelection({ key, id }); },
    refresh: () => { if (cancelWriting.current) return; setCancelReview(null); setCancelAck(false); requests.current.invalidate(); detailRequests.current.invalidate(); setAttempt(value => value + 1); } };
}
export type ExecutionReceiptsView = ReturnType<typeof useExecutionReceipts>;
