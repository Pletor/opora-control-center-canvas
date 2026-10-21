export const REVIEW_ROOT = "/api/oporahub/proposal-reviews";
export type ProposalKind = "spec" | "graph-addition" | "graph-change" | "content";
export type RiskLevel = "standard" | "elevated" | "critical";
export type ReviewScope = { project: string; workspace: string };
export type ReviewTarget = { proposalKind: ProposalKind; proposalId: string };
export type AcceptancePolicy = ReviewScope & { id: string; kind: "acceptance-policy"; schemaVersion: 1; enabled: boolean; parentPolicyRevision: string | null;
  rules: { requireAcknowledgementFrom: RiskLevel | "none"; blockOpenFindings: boolean } };
export type ReviewEvent = ReviewTarget & { id: string; kind: "proposal-review-event"; schemaVersion: 1; project: string; workspace: string; type: "comment" | "finding" | "resolve" | "ack";
  parentReviewEvent: string | null; by: { kind: "human" | "agent"; name: string }; createdAt: string; idempotencyKey: string;
  message?: string; anchor?: string | null; severity?: "info" | "warning" | "blocking";
  targetEventId?: string; resolution?: "resolved" | "accepted"; reason?: string;
  policyId?: string; risk?: RiskLevel; riskDigest?: string; parentAcceptedHead?: string | null; reviewHead?: string | null };
export type ReviewContext = ReviewTarget & { parentAcceptedHead: string | null; acceptedHead: string | null;
  risk: { level: RiskLevel; reasons: string[]; digest: string }; policyHead: string | null; policy: AcceptancePolicy | null;
  reviewHead: string | null; events: ReviewEvent[]; openFindings: ReviewEvent[]; acknowledgement: ReviewEvent | null;
  acknowledgementRequired: boolean; blockedReasons: string[]; eligible: boolean; identityPolicy: string; readOnly: boolean; canAccept: boolean; canComment: boolean; canAcknowledge: boolean; canResolve: boolean;
  receipt?: Record<string, unknown> | null; acceptedRevision?: string | null };
export type AcceptancePolicyContext = { policyHead: string | null; policy: AcceptancePolicy | null; acceptedHead: string | null; bootstrapException: string; readOnly: boolean; canConfigure: boolean };
export const riskLabels: Record<RiskLevel, string> = { standard: "Běžné", elevated: "Zvýšené", critical: "Kritické" };
export const reviewQuery = (scope: ReviewScope, target?: ReviewTarget) => new URLSearchParams({ ...scope, ...target }).toString();
export function reviewReady(model: { context: ReviewContext | null; busy: boolean; pending: boolean; error: string } | undefined,
  target: ReviewTarget, acceptedHead: string | null) {
  const value = model?.context;
  return !!value && !model!.busy && !model!.pending && !model!.error && value.proposalKind === target.proposalKind
    && value.proposalId === target.proposalId && value.acceptedHead === acceptedHead && value.parentAcceptedHead === acceptedHead
    && !value.readOnly && value.canAccept && value.eligible;
}
/** Scope/selection and action generation invalidate continuations before effect cleanup. */
export class ReviewRequests {
  private key = ""; private generation = 0; private writing = false;
  context(key: string) { if (key !== this.key) { this.key = key; this.invalidate(); } }
  invalidate() { this.generation++; }
  next() { const generation = ++this.generation; return () => generation === this.generation; }
  begin() { if (this.writing) return null; this.writing = true; return this.next(); }
  end() { this.writing = false; }
}
