/** Test-only records; no runtime demonstration data. */
import type { ReviewContext, ReviewEvent, AcceptancePolicyContext, AcceptancePolicy, ReviewTarget } from "./proposal-review";
import type { ProposalReviewView } from "./use-proposal-review";
export const reviewScope = { project: "project", workspace: "work" };
export const reviewTarget: ReviewTarget = { proposalKind: "content", proposalId: "a".repeat(40) };
export function reviewPolicy(): AcceptancePolicy {
  return { ...reviewScope, id: "c".repeat(40), kind: "acceptance-policy", schemaVersion: 1, enabled: true,
    parentPolicyRevision: null, rules: { requireAcknowledgementFrom: "elevated", blockOpenFindings: true } };
}
export function reviewContext(patch: Partial<ReviewContext> = {}): ReviewContext {
  return { ...reviewTarget, parentAcceptedHead: "b".repeat(40), acceptedHead: "b".repeat(40),
    risk: { level: "critical", reasons: ["First complete content adoption"], digest: "d".repeat(64) }, policyHead: null, policy: null,
    reviewHead: null, events: [], openFindings: [], acknowledgement: null, acknowledgementRequired: false, blockedReasons: [],
    eligible: true, identityPolicy: "Local names are not independent votes", canAccept: true, canComment: true, canAcknowledge: false,
    canResolve: true, readOnly: false, receipt: null, acceptedRevision: null, ...patch };
}
export function reviewEvent(patch: Partial<ReviewEvent> = {}): ReviewEvent {
  return { ...reviewScope, ...reviewTarget, id: "e".repeat(40), schemaVersion: 1, kind: "proposal-review-event", type: "finding",
    parentReviewEvent: null, by: { kind: "agent", name: "Agent" }, createdAt: "2026-10-21T12:00:00Z", idempotencyKey: "unique-key",
    message: "Check <script> value", anchor: "/changes/0/value", severity: "blocking", ...patch };
}
export function reviewModel(patch: Partial<ProposalReviewView> = {}): ProposalReviewView {
  return { ...reviewScope, key: "test", target: reviewTarget, context: reviewContext(), busy: false, pending: false,
    error: "", actionError: "", write: async () => {}, reset: () => {}, refresh: () => {}, ...patch };
}
export function acceptancePolicyContext(): AcceptancePolicyContext {
  return { policyHead: null, policy: null, acceptedHead: "b".repeat(40), bootstrapException: "Only the first baseline without any historical revision.",
    readOnly: false, canConfigure: true };
}
