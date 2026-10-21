export const BUDGET_ROOT = "/api/oporahub/execution-budgets";
export type BudgetLimits = { maxRunSeconds: number; maxAttempts: number; maxRepairRounds: number };
export type BudgetPolicy = { id: string; schemaVersion: 1; project: string; workspace: string; nodeId: string; acceptedRevision: string;
  parentPolicyHead: string | null; limits: BudgetLimits; by: { kind: string; name: string }; createdAt: string; requestId: string };
export type BudgetContext = { project: string; workspace: string; nodeId: string; acceptedHead: string | null; canConfigure: boolean; canCancel?: boolean; unavailableReason: string | null;
  enrolled: boolean; policyHead: string | null; policy: BudgetPolicy | null;
  family: { id: string; acceptedRevision: string; attempts: number; repairRounds: number; lastExecutionId: string | null; hasReported: boolean } | null;
  attemptsUsed: number; repairRoundsUsed: number; remainingAttempts: number | null; remainingRepairRounds: number | null; latestExecutionId: string | null; blockedReason: string | null };
export type BudgetHistory = { project: string; workspace: string; nodeId: string; acceptedHead: string | null;
  policies: BudgetPolicy[]; allocations: Record<string, unknown>[]; cancellations: Record<string, unknown>[]; canCancel: boolean; nextCursor: null };
export class BudgetRequests {
  private revision = 0;
  private writing = false;
  invalidate() { this.revision++; }
  next() { const ticket = ++this.revision; return () => ticket === this.revision; }
  begin() { if (this.writing) return null; this.writing = true; return this.next(); }
  end() { this.writing = false; }
  get busy() { return this.writing; }
}
export class BudgetIntent {
  private key = "";
  private id = "";
  constructor(private create: () => string = () => crypto.randomUUID()) {}
  request(payload: object) { const key = JSON.stringify(payload); if (key !== this.key) { this.key = key; this.id = this.create(); } return this.id; }
}
export function budgetPayload(context: BudgetContext, limits: BudgetLimits) {
  if (!context.canConfigure || !context.acceptedHead) throw new Error("Nastavení vyžaduje člověka a dostupnou přijatou revizi.");
  const { maxRunSeconds, maxAttempts, maxRepairRounds } = limits;
  if (![maxRunSeconds, maxAttempts, maxRepairRounds].every(Number.isSafeInteger) || maxRunSeconds < 30 || maxRunSeconds > 86400 || maxAttempts < 1 || maxAttempts > 100 || maxRepairRounds < 0 || maxRepairRounds >= maxAttempts)
    throw new Error("Doba musí být 30–86400 sekund, pokusy 1–100 a opravy 0 až počet pokusů minus jedna; pouze celá čísla.");
  return { project: context.project, workspace: context.workspace, nodeId: context.nodeId, expectedPolicyHead: context.policyHead,
    expectedAcceptedHead: context.acceptedHead, limits: { maxRunSeconds, maxAttempts, maxRepairRounds } };
}
export async function postBudget<T>(path: string, payload: object, transport: typeof fetch = fetch): Promise<T> {
  const session = await transport("/api/access/ui-session", { cache: "no-store" });
  if (!session.ok) throw new Error("Lidská relace není dostupná.");
  const result = await transport(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (!result.ok) { const body = await result.json().catch(() => null); throw new Error(typeof body?.error === "string" ? body.error : `Požadavek odmítnut (HTTP ${result.status}).`); }
  return result.json() as Promise<T>;
}
