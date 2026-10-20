import { useEffect, useRef, useState } from "react";
import { api, type CanvasNode } from "@/shared/types/logic/types";
import { ReceiptRequests, readExecutionHistory, readExecutionReceipts, type ExecutionContext, type ExecutionSummary, type ExecutionReceipt } from "./execution-receipts";

type State = { key: string; context: ExecutionContext | null; executions: ExecutionSummary[]; busy: boolean; error: string };
const empty = (key: string): State => ({ key, context: null, executions: [], busy: false, error: "" });
const message = (error: unknown) => error instanceof Error ? error.message : String(error);

export function useExecutionReceipts(project: string, workspace: string, nodes: CanvasNode[], enabled: boolean, refreshRevision: number) {
  const choices = nodes.filter(node => node.kind === "node" || node.kind === "sector");
  const scope = JSON.stringify([project, workspace]);
  const [card, setCard] = useState({ scope, id: "" });
  const nodeId = card.scope === scope && choices.some(node => node.id === card.id) ? card.id : choices[0]?.id ?? "";
  const [attempt, setAttempt] = useState(0);
  const key = JSON.stringify([scope, nodeId, enabled, refreshRevision, attempt]);
  const active = useRef(key);
  const requests = useRef(new ReceiptRequests());
  if (active.current !== key) { active.current = key; requests.current.invalidate(); }
  const [state, setState] = useState(() => empty(key));
  const shown = state.key === key ? state : empty(key);
  const [selection, setSelection] = useState({ key, id: "" });
  const selected = shown.executions.find(item => selection.key === key && item.executionId === selection.id) ?? shown.executions[0] ?? null;
  const id = selected?.executionId ?? "";
  const detailKey = JSON.stringify([key, id]);
  const detailActive = useRef(detailKey);
  const detailRequests = useRef(new ReceiptRequests());
  if (detailActive.current !== detailKey) { detailActive.current = detailKey; detailRequests.current.invalidate(); }
  const [detail, setDetail] = useState({ key: detailKey, receipts: [] as ExecutionReceipt[], busy: false, error: "" });
  const shownDetail = detail.key === detailKey ? detail : { key: detailKey, receipts: [], busy: !!id, error: "" };

  useEffect(() => {
    const valid = requests.current.next();
    if (!enabled || !nodeId) { setState(empty(key)); return; }
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

  return { ...shown, choices, nodeId, project, workspace, selected, receipts: shownDetail.receipts,
    detailBusy: shownDetail.busy, detailError: shownDetail.error,
    selectCard: (id: string) => setCard({ scope, id }),
    selectExecution: (id: string) => setSelection({ key, id }),
    refresh: () => { requests.current.invalidate(); detailRequests.current.invalidate(); setAttempt(value => value + 1); } };
}
export type ExecutionReceiptsView = ReturnType<typeof useExecutionReceipts>;
