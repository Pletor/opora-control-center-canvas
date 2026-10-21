import { describe, expect, it, vi } from "vitest";
import { ReviewRequests, reviewReady } from "./proposal-review";
import { parseReview, parseReviewEvent, parseAcceptancePolicy } from "./review-parse";
import { reviewContext, reviewEvent, reviewModel, reviewPolicy, reviewScope, reviewTarget, acceptancePolicyContext } from "./review-fixtures";
import { postReview } from "./review-api";

describe("exact proposal review", () => {
  it("supports all four exact proposal kinds including first graph with a known null head", () => {
    for (const kind of ["spec", "graph-addition", "graph-change", "content"] as const) {
      const context = reviewContext({ proposalKind: kind, parentAcceptedHead: null, acceptedHead: null });
      const target = { ...reviewTarget, proposalKind: kind };
      expect(parseReview(context, reviewScope, target).acceptedHead).toBeNull();
      expect(reviewReady(reviewModel({ context }), target, null)).toBe(true);
    }
    expect(reviewReady(undefined, reviewTarget, null)).toBe(false);
  });
  it("rejects changed scope, wrong ID, broken chain and phantom permission", () => {
    const finding = reviewEvent();
    expect(() => parseReviewEvent(finding, { ...reviewScope, workspace: "other" }, reviewTarget)).toThrow();
    for (const patch of [{ proposalId: "f".repeat(40) }, { eligible: true, blockedReasons: ["Blocked"] },
      { reviewHead: finding.id }, { events: [finding], openFindings: [], reviewHead: finding.id },
      { readOnly: true, canAccept: true }]) expect(() => parseReview({ ...reviewContext(), ...patch }, reviewScope, reviewTarget)).toThrow();
  });
  it("accepts an active-policy critical first graph acknowledgement before any accepted revision", () => {
    const target = { ...reviewTarget, proposalKind: "graph-addition" as const }, policy = reviewPolicy();
    const ack = reviewEvent({ ...target, type: "ack", by: { kind: "human", name: "Human" }, policyId: policy.id,
      risk: "critical", riskDigest: "d".repeat(64), parentAcceptedHead: null, reviewHead: null });
    const context = reviewContext({ ...target, acceptedHead: null, parentAcceptedHead: null, policy, policyHead: policy.id,
      acknowledgementRequired: true, acknowledgement: ack, events: [ack], reviewHead: ack.id, canAcknowledge: true });
    expect(parseReview(context, reviewScope, target).acknowledgement?.parentAcceptedHead).toBeNull();
    expect(reviewReady(reviewModel({ context }), target, null)).toBe(true);
  });
  it("cannot accept open blocking findings under an active policy", () => {
    const finding = reviewEvent(), policy = reviewPolicy();
    const value = reviewContext({ policy, policyHead: policy.id, events: [finding], reviewHead: finding.id, openFindings: [finding],
      acknowledgementRequired: true, blockedReasons: ["Blocking finding", "ACK missing"], eligible: false, canAccept: false, canAcknowledge: true });
    expect(parseReview(value, reviewScope, reviewTarget).openFindings).toHaveLength(1);
    expect(reviewReady(reviewModel({ context: value }), reviewTarget, value.acceptedHead)).toBe(false);
    expect(() => parseReview({ ...value, blockedReasons: [], eligible: true }, reviewScope, reviewTarget)).toThrow();
  });
  it("binds risk ACK to exact classifier digest, policy, origin and final review event", () => {
    const policy = reviewPolicy(), base = reviewContext();
    const ack = reviewEvent({ type: "ack", by: { kind: "human", name: "Human" }, policyId: policy.id,
      risk: base.risk.level, riskDigest: base.risk.digest, parentAcceptedHead: base.acceptedHead, reviewHead: null });
    const context = reviewContext({ policy, policyHead: policy.id, acknowledgementRequired: true, events: [ack], reviewHead: ack.id, acknowledgement: ack });
    expect(parseReview(context, reviewScope, reviewTarget).acknowledgement?.id).toBe(ack.id);
    for (const patch of [{ risk: { ...context.risk, digest: "f".repeat(64) } }, { policyHead: "f".repeat(40) }, { acceptedHead: "f".repeat(40) }])
      expect(() => parseReview({ ...context, ...patch }, reviewScope, reviewTarget)).toThrow();
    expect(() => parseReviewEvent({ ...ack, by: { kind: "agent", name: "Agent" } }, reviewScope, reviewTarget)).toThrow();
  });
  it("keeps loaded absent/disabled policy legacy semantics and validates permissions", () => {
    expect(parseReview(reviewContext(), reviewScope, reviewTarget).eligible).toBe(true);
    expect(parseAcceptancePolicy(acceptancePolicyContext(), reviewScope).policy).toBeNull();
    expect(() => parseAcceptancePolicy({ ...acceptancePolicyContext(), readOnly: true }, reviewScope)).toThrow();
    const policy = { ...reviewPolicy(), enabled: false };
    expect(parseReview(reviewContext({ policy, policyHead: policy.id }), reviewScope, reviewTarget).eligible).toBe(true);
  });
  it("fences stale reads/writes and does not retry uncertain event delivery", async () => {
    const requests = new ReviewRequests(); requests.context("scope/id");
    const old = requests.next(); requests.context("other/id"); expect(old()).toBe(false);
    const write = requests.begin()!; expect(requests.begin()).toBeNull(); requests.invalidate(); expect(write()).toBe(false); requests.end();
    const transport = vi.fn().mockResolvedValueOnce(Response.json({ ok: true })).mockRejectedValueOnce(new Error("Uncertain"));
    await expect(postReview("/events", { idempotencyKey: "one-explicit-action" }, transport)).rejects.toThrow("Uncertain");
    expect(transport).toHaveBeenCalledTimes(2);
  });
});
