import { useEffect, useMemo, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { useAgentState } from "@/hub/oporahub-agent-state/logic/use-agent-state";
import { useHubRead } from "@/hub/oporahub-mirror/logic/use-hub-read";
import { isObject, scopeQuery } from "@/hub/oporahub-mirror/logic/hub-read";
import { BUDGET_ROOT, type BudgetContext } from "@/hub/execution-budgets/logic/execution-budgets";
import type { ExecutionReceipt, ExecutionSummary } from "@/hub/execution-receipts/logic/execution-receipts";
import type { PlanChangeset, PlanContext } from "@/hub/plan-changes/logic/plan-changes";
import { cardGates, gatesEndpoint, parseGates } from "@/hub/oporahub-review-gate/logic/review-gate";
import { latestExecution } from "../run-tab/logic/run-view";
import { parseFindings, reviewJobsUrl } from "../review-tab/logic/review-view";
import { collectStepResults, withBackendSteps } from "../steps-tab/logic/step-status";
import { cardEntry } from "./card-header";
import { useCardEvents } from "./use-card-events";

// Data jednoho otevřeného detailu: snímek agent-state (sdílený poller) a jednorázová čtení detailů
// při otevření a po „Obnovit“. Nic z toho nepolluje; zápisy jdou přes původní API s lidskou session.
function shape<T>(label: string, check: (raw: Record<string, unknown>) => boolean) {
  return (raw: unknown): T => { if (!isObject(raw) || !check(raw)) throw new Error(`${label} má neplatný tvar.`); return raw as T; };
}
const parseContext = shape<PlanContext>("Kontext zadání", raw => Array.isArray(raw.documents) && Array.isArray(raw.acceptedDocuments));
const parseChangesets = shape<{ items: PlanChangeset[] }>("Historie návrhů", raw => Array.isArray(raw.items));
const parseExecutions = shape<{ executions: ExecutionSummary[] }>("Historie běhů", raw => Array.isArray(raw.executions));
const parseReceipts = shape<{ results: ExecutionReceipt[] }>("Výsledky běhu", raw => Array.isArray(raw.results));
const parseBudget = shape<BudgetContext>("Rozpočet karty", raw => typeof raw.nodeId === "string");
type ProcessItem = { nodeId: string; acceptanceEvidence?: unknown; doneConfirmed?: unknown };
const parseProcess = shape<{ items: ProcessItem[] }>("Proces karet", raw => Array.isArray(raw.items));

/** Prohlížeč potřebuje lidskou UI session i pro čtení běhů a rozpočtů; jednou na otevření detailu. */
function useUiSession() {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let live = true;
    api("/api/access/ui-session").catch(() => null).finally(() => { if (live) setReady(true); });
    return () => { live = false; };
  }, []);
  return ready;
}

export function useCardData(project: string, workspace: string, nodeId: string) {
  const agent = useAgentState(project, workspace);
  const session = useUiSession();
  const scoped = !!project && !!workspace && !!nodeId;
  const query = scopeQuery({ project, workspace }), nodeQuery = scopeQuery({ project, workspace, nodeId });
  const context = useHubRead(scoped && session ? `/api/oporahub/changesets/context?${query}` : null, parseContext);
  const changesets = useHubRead(scoped && session ? `/api/oporahub/changesets?${query}` : null, parseChangesets);
  const executions = useHubRead(scoped && session ? `/api/oporahub/executions?${nodeQuery}` : null, parseExecutions);
  const latest = latestExecution(executions.data?.executions ?? [], nodeId);
  const receipts = useHubRead(latest ? `/api/oporahub/executions/${encodeURIComponent(latest.executionId)}/results?${query}` : null, parseReceipts);
  const budget = useHubRead(scoped && session ? `${BUDGET_ROOT}?${nodeQuery}` : null, parseBudget);
  const gates = useHubRead(scoped && session ? gatesEndpoint(project, workspace) : null, parseGates);
  const findings = useHubRead(scoped && session ? reviewJobsUrl(project, workspace) : null, parseFindings);
  // Akceptace karty doložená proti přijatému zadání (docs/oporahub-plan-steps.md) a lidské uzavření nese process-sync.
  const process = useHubRead(scoped && session ? `/api/oporahub/process?${query}` : null, parseProcess);
  const processCard = process.data?.items.find(item => item.nodeId === nodeId) ?? null;
  const events = useCardEvents(project, workspace, nodeId);
  // Odpočet lease se počítá od chvíle, kdy přišel `serverNow` (čas klienta v sekundách).
  const [loadedAt, setLoadedAt] = useState(() => Date.now() / 1000);
  useEffect(() => { if (executions.data) setLoadedAt(Date.now() / 1000); }, [executions.data]);

  const card = cardEntry(agent.state, nodeId);
  const accepted = context.data?.acceptedDocuments.find(item => item.nodeId === nodeId) ?? null;
  const working = context.data?.documents.find(item => item.nodeId === nodeId) ?? null;
  const mine = (changesets.data?.items ?? []).filter(item => item.changes.some(change => change.nodeId === nodeId));
  const gate = cardGates(gates.data ?? [], nodeId)[0] ?? null;
  // Stav kroků: agent-state přes všechny běhy; důkazy z výsledků nejnovějšího běhu.
  const backendSteps = card?.steps?.items;
  const stepResults = useMemo(() => withBackendSteps(collectStepResults(receipts.data?.results ?? []), backendSteps), [receipts.data, backendSteps]);
  // 409 u review = automatické review je vypnuté (review_jobs_disabled); záložka to řekne sama, není to chyba.
  const reviewError = (error: string) => error.includes("HTTP 409") ? "" : error;
  const errors = [context.error, changesets.error, executions.error, receipts.error, budget.error, reviewError(gates.error), reviewError(findings.error),
    events.error, agent.error].filter(Boolean);
  const busy = context.busy || changesets.busy || executions.busy || gates.busy || events.busy;
  function reload() {
    agent.refresh(); process.reload(); context.reload(); changesets.reload(); executions.reload(); receipts.reload(); budget.reload(); gates.reload(); findings.reload(); events.reload();
  }
  return {
    agent: agent.state, card, context: context.data, accepted, working, changesets: mine, executions: executions.data?.executions ?? [],
    latest, receipts: receipts.data?.results ?? [], stepResults, budget: budget.data?.nodeId === nodeId ? budget.data : null,
    gate, findings: findings.data ?? [], events, loadedAt, busy, errors, reload,
    acceptance: typeof processCard?.acceptanceEvidence === "boolean" ? processCard.acceptanceEvidence : null,
    closed: processCard?.doneConfirmed === true,
  };
}
export type CardData = ReturnType<typeof useCardData>;
