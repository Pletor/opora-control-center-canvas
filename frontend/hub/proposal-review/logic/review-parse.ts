import type { AcceptancePolicy, AcceptancePolicyContext, ReviewContext, ReviewEvent, ReviewScope, ReviewTarget } from "./proposal-review";
type ObjectValue = Record<string, unknown>;
const object = (value: unknown): value is ObjectValue => !!value && typeof value === "object" && !Array.isArray(value);
const text = (value: unknown, max: number): value is string => typeof value === "string" && value.length <= max;
const hash = (value: unknown, n = 40): value is string => typeof value === "string" && new RegExp(`^[a-f0-9]{${n}}$`).test(value);
const nullableHash = (value: unknown) => value === null || hash(value);
const level = (value: unknown) => ["standard", "elevated", "critical"].includes(String(value));
const strings = (value: unknown, count: number, size: number): value is string[] => Array.isArray(value) && value.length <= count && value.every(item => text(item, size));
const fail = (): never => { throw new Error("Podklady review návrhu nejsou úplné nebo mají neplatný formát."); };
function policy(value: unknown): value is AcceptancePolicy {
  return object(value) && hash(value.id) && value.kind === "acceptance-policy" && value.schemaVersion === 1 && nullableHash(value.parentPolicyRevision)
    && typeof value.enabled === "boolean" && object(value.rules) && (level(value.rules.requireAcknowledgementFrom) || value.rules.requireAcknowledgementFrom === "none")
    && typeof value.rules.blockOpenFindings === "boolean";
}
export function parseReviewEvent(value: unknown, scope: ReviewScope, target: ReviewTarget): ReviewEvent {
  if (!object(value) || value.kind !== "proposal-review-event" || value.schemaVersion !== 1 || !hash(value.id)
    || value.project !== scope.project || value.workspace !== scope.workspace || value.proposalKind !== target.proposalKind || value.proposalId !== target.proposalId
    || !nullableHash(value.parentReviewEvent) || !text(value.idempotencyKey, 128) || !value.idempotencyKey
    || !object(value.by) || !["human", "agent"].includes(String(value.by.kind)) || !text(value.by.name, 120)
    || !text(value.createdAt, 80) || !Number.isFinite(Date.parse(value.createdAt))) return fail();
  if (value.type === "comment" || value.type === "finding") {
    if (!text(value.message, 8000) || !value.message.trim() || !(value.anchor === null || text(value.anchor, 2048))) return fail();
    if (value.type === "finding" && !["info", "warning", "blocking"].includes(String(value.severity))) return fail();
  } else if (value.type === "resolve") {
    if (value.by.kind !== "human" || !hash(value.targetEventId) || !["resolved", "accepted"].includes(String(value.resolution)) || !text(value.reason, 8000) || !value.reason.trim()) return fail();
  } else if (value.type === "ack") {
    if (value.by.kind !== "human" || !hash(value.policyId) || !level(value.risk) || !hash(value.riskDigest, 64)
      || !nullableHash(value.parentAcceptedHead) || value.reviewHead !== value.parentReviewEvent) return fail();
  } else return fail();
  return value as unknown as ReviewEvent;
}
export function parseReview(value: unknown, scope: ReviewScope, target: ReviewTarget): ReviewContext {
  if (!object(value) || value.proposalKind !== target.proposalKind || value.proposalId !== target.proposalId
    || !nullableHash(value.parentAcceptedHead) || !nullableHash(value.acceptedHead) || !nullableHash(value.policyHead) || !nullableHash(value.reviewHead)
    || !object(value.risk) || !level(value.risk.level) || !hash(value.risk.digest, 64) || !strings(value.risk.reasons, 32, 2000) || !value.risk.reasons.length
    || !(value.policy === null || policy(value.policy)) || (value.policy === null ? value.policyHead !== null : value.policy.id !== value.policyHead)
    || !Array.isArray(value.events) || value.events.length > 2048 || !Array.isArray(value.openFindings) || value.openFindings.length > 2048
    || !strings(value.blockedReasons, 32, 2000) || !text(value.identityPolicy, 2000)
    || !["eligible", "canAccept", "canComment", "canAcknowledge", "canResolve", "readOnly", "acknowledgementRequired"].every(key => typeof value[key] === "boolean")) return fail();
  if (value.readOnly && (value.canAccept || value.canComment || value.canResolve || value.canAcknowledge)) return fail();
  if (value.policy && (value.policy.project !== scope.project || value.policy.workspace !== scope.workspace)) return fail();
  const events = value.events.map(item => parseReviewEvent(item, scope, target));
  if (new Set(events.map(item => item.id)).size !== events.length || (events.at(-1)?.id ?? null) !== value.reviewHead) return fail();
  for (let index = 0; index < events.length; index++) if (events[index].parentReviewEvent !== (events[index - 1]?.id ?? null)) return fail();
  const open = value.openFindings.map(item => parseReviewEvent(item, scope, target));
  const resolved = new Set(events.filter(item => item.type === "resolve").map(item => item.targetEventId));
  const expected = events.filter(item => item.type === "finding" && !resolved.has(item.id));
  if (JSON.stringify(open) !== JSON.stringify(expected)) return fail();
  const ack = value.acknowledgement === null ? null : parseReviewEvent(value.acknowledgement, scope, target);
  if (ack && (ack.type !== "ack" || ack.id !== value.reviewHead || ack.policyId !== value.policyHead || ack.riskDigest !== value.risk.digest
    || ack.risk !== value.risk.level || ack.parentAcceptedHead !== value.acceptedHead || value.parentAcceptedHead !== value.acceptedHead)) return fail();
  const blocked = value.blockedReasons.length > 0;
  if (value.policy?.enabled && value.policy.rules.blockOpenFindings && open.some(item => item.severity === "blocking") && value.eligible) return fail();
  if ((value.eligible && (blocked || value.parentAcceptedHead !== value.acceptedHead)) || (value.canAccept && !value.eligible)
    || (value.acknowledgementRequired && !ack && value.eligible)) return fail();
  if (!nullableHash(value.acceptedRevision)) return fail();
  if (value.receipt !== null) {
    const receipt = value.receipt;
    if (!object(receipt) || receipt.kind !== "acceptance-receipt" || receipt.schemaVersion !== 1 || !hash(receipt.id)
      || receipt.project !== scope.project || receipt.workspace !== scope.workspace || receipt.acceptedRevision !== value.acceptedRevision
      || receipt.proposalKind !== target.proposalKind || receipt.proposalId !== target.proposalId || receipt.bootstrap !== false
      || !hash(receipt.policyId) || !level(receipt.risk) || !strings(receipt.reasons, 32, 2000)
      || !nullableHash(receipt.reviewHead) || !nullableHash(receipt.ackId)) return fail();
  }
  return { ...value, events, openFindings: open, acknowledgement: ack } as unknown as ReviewContext;
}
export function parseAcceptancePolicy(value: unknown, scope: ReviewScope): AcceptancePolicyContext {
  if (!object(value) || !nullableHash(value.policyHead) || !nullableHash(value.acceptedHead) || typeof value.canConfigure !== "boolean" || typeof value.readOnly !== "boolean"
    || !text(value.bootstrapException, 2000) || !(value.policy === null || policy(value.policy))
    || (value.policy === null ? value.policyHead !== null : value.policy.id !== value.policyHead)) return fail();
  if (value.policy && (value.policy.project !== scope.project || value.policy.workspace !== scope.workspace)) return fail();
  if (value.readOnly && value.canConfigure) return fail();
  return value as unknown as AcceptancePolicyContext;
}
