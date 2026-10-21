export type ExecutionSummary = {
  executionId: string; project: string; workspace: string; nodeId: string; epoch: number;
  acceptedRevision: string; assignmentDigest: string; expiresAt: number; serverNow: number;
  state: "running" | "released" | "reported" | "revoked" | "cancelled"; createdAt?: string; owner?: string;
  executionProtocolVersion?: 1 | 2;
  budget?: { policyHead: string; familyId: string; allocationId: string; attempt: number; repairRound: number; kind: "initial" | "retry" | "repair"; admittedAt: number; runDeadlineAt: number; maxRunSeconds: number };
};
export type ExecutionReceipt = {
  receiptId: string; executionId: string; requestId: string; result: { summary: string; [key: string]: unknown };
  state: "reported"; acceptedRevision: string; assignmentDigest: string; verification: string; createdAt: string;
};
export type ExecutionContext = {
  available: boolean; unavailableReason: string | null; acceptedHead: string | null; contextVersion: string | null;
};
export type ExecutionHistory = { executions: ExecutionSummary[]; canCancel?: boolean };
export type ReceiptHistory = { results: ExecutionReceipt[] };
export type ReadApi = <T>(url: string) => Promise<T>;

export class ReceiptRequests {
  private version = 0;
  next() { const version = ++this.version; return () => version === this.version; }
  invalidate() { this.version++; }
}

export function executionQuery(project: string, workspace: string, nodeId?: string) {
  return new URLSearchParams({ project, workspace, ...(nodeId ? { nodeId } : {}) }).toString();
}

export async function readExecutionHistory(read: ReadApi, project: string, workspace: string, nodeId = "") {
  // These GET endpoints require identified UI even before the first write in a fresh browser.
  await read("/api/access/ui-session");
  const query = executionQuery(project, workspace, nodeId);
  const [context, history] = await Promise.allSettled([
    nodeId ? read<ExecutionContext>(`/api/oporahub/executions/context?${query}`) : Promise.resolve(null),
    read<ExecutionHistory>(`/api/oporahub/executions?${query}`),
  ]);
  if (history.status === "rejected") throw history.reason;
  return { context: context.status === "fulfilled" ? context.value : null, executions: history.value.executions, canCancel: !!history.value.canCancel,
    error: context.status === "rejected" ? `Kontext karty není dostupný; historie zůstává přístupná. ${context.reason instanceof Error ? context.reason.message : String(context.reason)}` : "" };
}

export async function readExecutionReceipts(read: ReadApi, project: string, workspace: string, id: string) {
  await read("/api/access/ui-session");
  return read<ReceiptHistory>(`/api/oporahub/executions/${encodeURIComponent(id)}/results?${executionQuery(project, workspace)}`);
}

export function executionLabel(execution: ExecutionSummary) {
  if (execution.state === "running") {
    if (!Number.isFinite(execution.expiresAt) || !Number.isFinite(execution.serverNow)) return "Autorita nedoložena";
    return execution.expiresAt > execution.serverNow ? "Aktivní při načtení" : "Oprávnění vypršelo";
  }
  return ({ released: "Uvolněno", reported: "Výsledek nahlášen", revoked: "Oprávnění již neplatí", cancelled: "Lidsky zrušeno" } as Record<string, string>)[execution.state] ?? "Neznámý stav";
}

export function unixTime(value: number) {
  return Number.isFinite(value) && !Number.isNaN(new Date(value * 1000).valueOf())
    ? new Date(value * 1000).toLocaleString("cs-CZ") : "Čas není dostupný";
}

export function receiptDetails(receipt: ExecutionReceipt) {
  const details = Object.fromEntries(Object.entries(receipt.result).filter(([key]) => key !== "summary"));
  return Object.keys(details).length ? JSON.stringify(details, null, 2) : "";
}
