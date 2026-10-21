import { useEffect, useRef, useState } from "react";
import { api, type CanvasNode } from "@/shared/types/logic/types";
import { BUDGET_ROOT, BudgetIntent, BudgetRequests, budgetPayload, postBudget, type BudgetContext, type BudgetHistory, type BudgetLimits } from "./execution-budgets";

const message = (error: unknown) => error instanceof Error ? error.message : String(error);
export function useExecutionBudgets(project: string, workspace: string, nodes: CanvasNode[], enabled: boolean, acceptedRevision: number) {
  const scope = JSON.stringify([project, workspace]);
  const choices = nodes.filter(node => node.kind === "node" || node.kind === "sector");
  const [selection, setSelection] = useState({ scope, id: "" });
  const nodeId = selection.scope === scope && choices.some(node => node.id === selection.id) ? selection.id : choices[0]?.id ?? "";
  const [attempt, setAttempt] = useState(0), [writing, setWriting] = useState(false);
  const key = JSON.stringify([scope, nodeId, enabled, acceptedRevision, attempt]);
  const active = useRef(key), requests = useRef(new BudgetRequests()), intent = useRef(new BudgetIntent());
  if (active.current !== key) { active.current = key; requests.current.invalidate(); }
  const empty = { key, context: null as BudgetContext | null, history: [] as BudgetHistory["policies"], ledger: null as BudgetHistory | null, busy: false, error: "" };
  const [state, setState] = useState(empty), [limits, setLimits] = useState<BudgetLimits>({ maxRunSeconds: 900, maxAttempts: 3, maxRepairRounds: 1 });
  const [pending, setPending] = useState<{ key: string; payload: ReturnType<typeof budgetPayload> & { requestId: string }; fingerprint: string } | null>(null), [ack, setAck] = useState("");
  const shown = state.key === key ? state : empty;
  const reviewKey = JSON.stringify([key, shown.context?.policyHead, shown.context?.acceptedHead]);
  const review = pending?.key === reviewKey ? pending : null;
  const disabled = writing || shown.busy || !!shown.error || !shown.context?.canConfigure;
  useEffect(() => {
    const valid = requests.current.next(); if (!enabled || !nodeId) return;
    setState({ ...empty, busy: true });
    void (async () => {
      try {
        await api("/api/access/ui-session");
        const query = new URLSearchParams({ project, workspace, nodeId });
        const [context, history] = await Promise.allSettled([api<BudgetContext>(`${BUDGET_ROOT}?${query}`), api<BudgetHistory>(`${BUDGET_ROOT}/history?${query}`)]);
        if (!valid()) return;
        const current = context.status === "fulfilled" ? context.value : null;
        const ledger = history.status === "fulfilled" ? history.value : null;
        if (current && ledger && (current.project !== ledger.project || current.workspace !== ledger.workspace || current.nodeId !== ledger.nodeId || current.acceptedHead !== ledger.acceptedHead)) {
          setState({ ...empty, error: "Kontext a historie mají různý scope nebo přijatou revizi. Obnovte podklady." }); return;
        }
        setState({ key, context: current, ledger, history: ledger?.policies ?? [], busy: false,
          error: [context, history].filter(result => result.status === "rejected").map(result => message((result as PromiseRejectedResult).reason)).join(" ") });
      } catch (error) { if (valid()) setState({ ...empty, error: message(error) }); }
    })();
    return () => requests.current.invalidate();
  }, [key, project, workspace, nodeId, enabled]);
  function prepare() {
    if (disabled || !shown.context) return;
    try { const base = budgetPayload(shown.context, limits), payload = { ...base, requestId: intent.current.request(base) };
      setPending({ key: reviewKey, payload, fingerprint: JSON.stringify(payload) }); setAck("");
    } catch (error) { setState({ ...shown, error: message(error) }); }
  }
  async function save() {
    if (disabled || !review || ack !== review.fingerprint) return;
    const valid = requests.current.begin(); if (!valid) return; setWriting(true); setAck("");
    try { await postBudget(BUDGET_ROOT, review.payload); if (valid()) { setPending(null); setAttempt(value => value + 1); } }
    catch (error) { if (valid()) { setPending(null); setState({ ...shown, error: message(error) + " Zápis se neopakuje automaticky. Obnovte stav před dalším potvrzením." }); } }
    finally { requests.current.end(); setWriting(false); }
  }
  return { ...shown, busy: shown.busy || writing, project, workspace, nodeId, choices, limits, review, disabled, confirmed: !!review && ack === review.fingerprint,
    select: (id: string) => { if (!writing) { setPending(null); setAck(""); setSelection({ scope, id }); } },
    edit: (field: keyof BudgetLimits, value: number) => { setPending(null); setAck(""); setLimits(old => ({ ...old, [field]: value })); },
    prepare, save, confirm: (value: boolean) => setAck(value && review ? review.fingerprint : ""), cancel: () => { setPending(null); setAck(""); },
    refresh: () => { if (!requests.current.busy) { requests.current.invalidate(); setPending(null); setAck(""); setAttempt(value => value + 1); } } };
}
export type ExecutionBudgetsView = ReturnType<typeof useExecutionBudgets>;
