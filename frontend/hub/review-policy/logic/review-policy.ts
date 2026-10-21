export type PolicyRules = { requiredChecks: { appId: number; name: string }[]; reviewerIds: number[];
  minimumCodeApprovals: number; minimumPlanApprovals: number; maxObservationAgeSeconds: number };
export type PolicyRevision = { id: string; schemaVersion: 1; project: string; workspace: string; kind: "review-policy";
  parentPolicyRevision: string | null; enabled: boolean; repository: { id: number; fullName: string; baseBranch: string };
  identityEvidenceId: string; rules: PolicyRules; by: { kind: "human"; name: string }; createdAt: string };
export type PolicyContext = { project: string; workspace: string; policyHead: string | null; policy: PolicyRevision | null;
  canConfigure: boolean; unavailableReason: string | null; acceptedHead: string | null };
export type PolicyHistory = { policyHead: string | null; items: PolicyRevision[] };
type ReviewAssessment = { status: "approved" | "changes_requested" | "missing" | "unknown"; minimum: number | null; reviewIds: number[]; reviewerIds: number[] };
export type PolicyEvaluation = { evaluatorVersion: 1; status: "not_configured" | "disabled" | "unknown" | "blocked" | "satisfied";
  policyRevision: string | null; evidenceId: string | null; attemptSequence: number | null;
  binding: { acceptedRevision: string | null; repositoryId: number | null; prId: number | null; headRepoId: number | null; headSha: string | null; baseSha: string | null; baseBranch: string | null };
  checks: { policyVerified: boolean; required: { appId: number; name: string; status: "passed" | "missing" | "pending" | "failed" | "unknown"; runId: number | null }[] };
  codeReview: ReviewAssessment; planReview: ReviewAssessment;
  freshness: { currentEligible: boolean; observedFrom: string | null; observedUntil: string | null; expiresAt: string | null;
    evaluatedAt: string; remoteFreshness: "historical-observation" }; blockers: string[] };
export type PolicyDraft = { identityEvidenceId: string; checks: { appId: string; name: string }[]; reviewerIds: string;
  codeMinimum: string; planMinimum: string; age: string };
export const emptyPolicyDraft = (): PolicyDraft => ({ identityEvidenceId: "", checks: [{ appId: "", name: "" }], reviewerIds: "", codeMinimum: "1", planMinimum: "1", age: "300" });
export function policyDraft(policy: PolicyRevision): PolicyDraft {
  return { identityEvidenceId: policy.identityEvidenceId, checks: policy.rules.requiredChecks.map(check => ({ appId: String(check.appId), name: check.name })),
    reviewerIds: policy.rules.reviewerIds.join(", "), codeMinimum: String(policy.rules.minimumCodeApprovals), planMinimum: String(policy.rules.minimumPlanApprovals), age: String(policy.rules.maxObservationAgeSeconds) };
}
function positive(value: string, label: string) {
  if (!/^[1-9][0-9]*$/.test(value.trim()) || !Number.isSafeInteger(Number(value))) throw new Error(`${label}: zadejte kladné celé číslo.`);
  return Number(value);
}
export function policyPayload(project: string, workspace: string, context: PolicyContext, draft: PolicyDraft) {
  if (!context.canConfigure) throw new Error(context.unavailableReason || "Pravidla může nastavit pouze člověk v zapisovatelném projektu.");
  if (!/^[a-f0-9]{40}$/.test(draft.identityEvidenceId)) throw new Error("Vyberte úplné serverové pozorování pro identitu repozitáře.");
  const requiredChecks = draft.checks.map(check => ({ appId: positive(check.appId, "ID aplikace"), name: check.name }));
  if (!requiredChecks.length || requiredChecks.length > 32 || requiredChecks.some(check => !check.name.trim() || check.name.length > 255)
    || new Set(requiredChecks.map(check => JSON.stringify([check.appId, check.name]))).size !== requiredChecks.length)
    throw new Error("Vyberte 1 až 32 různých dvojic ID aplikace a přesného názvu kontroly.");
  const reviewerIds = draft.reviewerIds.split(/[\s,;]+/).filter(Boolean).map(value => positive(value, "ID účtu reviewera"));
  if (!reviewerIds.length || reviewerIds.length > 100 || new Set(reviewerIds).size !== reviewerIds.length) throw new Error("Zadejte 1 až 100 jedinečných číselných ID účtů reviewerů.");
  const minimumCodeApprovals = positive(draft.codeMinimum, "Minimum schválení kódu"), minimumPlanApprovals = positive(draft.planMinimum, "Minimum schválení zadání");
  const maxObservationAgeSeconds = positive(draft.age, "Platnost pozorování");
  if (Math.max(minimumCodeApprovals, minimumPlanApprovals) > reviewerIds.length) throw new Error("Minimum schválení nesmí přesáhnout počet povolených účtů.");
  if (maxObservationAgeSeconds < 30 || maxObservationAgeSeconds > 3600) throw new Error("Platnost pozorování musí být 30 až 3600 sekund.");
  return { project, workspace, expectedPolicyHead: context.policyHead, identityEvidenceId: draft.identityEvidenceId,
    rules: { requiredChecks, reviewerIds, minimumCodeApprovals, minimumPlanApprovals, maxObservationAgeSeconds } };
}
/** Confirmation is for one exact action, scope, CAS head and projected payload. */
export function policyConfirmation(action: "activate" | "disable", payload: object) { return JSON.stringify([action, payload]); }
export class PolicyRequests {
  private generation = 0;
  private writing = false;
  invalidate() { this.generation++; }
  next() { const ticket = ++this.generation; return () => ticket === this.generation; }
  beginWrite() { if (this.writing) return null; this.writing = true; return this.next(); }
  endWrite() { this.writing = false; }
  get busy() { return this.writing; }
}
/** Use server-relative age minus the entire request duration; a slow read cannot extend freshness. */
export function policyDeadline(value: PolicyEvaluation, startedAt: number, receivedAt: number) {
  const remaining = Date.parse(value.freshness.expiresAt ?? "") - Date.parse(value.freshness.evaluatedAt);
  return Number.isFinite(remaining) ? receivedAt + Math.max(0, remaining - (receivedAt - startedAt)) : receivedAt;
}
export function visiblePolicyStatus(value: PolicyEvaluation | null, deadline: number, now: number, invalidated = false): PolicyEvaluation["status"] {
  if (!value || invalidated) return "unknown";
  if (value.status === "not_configured" || value.status === "disabled") return value.status;
  if ((value.freshness.expiresAt && now >= deadline) || (value.status === "satisfied" && (!value.freshness.currentEligible || !value.freshness.expiresAt || now >= deadline))) return "unknown";
  return value.status;
}
export const policyLabels: Record<PolicyEvaluation["status"], string> = { not_configured: "Pravidla nejsou nastavena", disabled: "Pravidla jsou vypnuta",
  unknown: "Aktuální splnění není doloženo", blocked: "Pravidla nejsou splněna", satisfied: "Pozorování splňuje tato místní pravidla" };
