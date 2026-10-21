import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { emptyPolicyDraft, policyConfirmation, policyDeadline, policyPayload, PolicyRequests, visiblePolicyStatus,
  type PolicyContext, type PolicyEvaluation } from "./review-policy";
import { postPolicy } from "./policy-api";
import PolicyStatus from "../components/PolicyStatus";
import type { PolicyStatusView } from "./use-policy-status";
import HistoricalPolicyAssessment from "../components/HistoricalPolicyAssessment";

const context: PolicyContext = { project: "p", workspace: "w", policyHead: null, policy: null, canConfigure: true, unavailableReason: null, acceptedHead: "a".repeat(40) };
const draft = () => ({ ...emptyPolicyDraft(), identityEvidenceId: "b".repeat(40), checks: [{ appId: "42", name: "exact check" }], reviewerIds: "123, 456" });
const evaluation: PolicyEvaluation = { evaluatorVersion: 1, status: "satisfied", policyRevision: "policy", evidenceId: "evidence", attemptSequence: 2,
  binding: { acceptedRevision: "accepted", repositoryId: 1, prId: 2, headRepoId: 1, headSha: "c".repeat(40), baseSha: "d".repeat(40), baseBranch: "main" },
  checks: { policyVerified: true, required: [{ appId: 42, name: "exact check", status: "passed", runId: 8 }] },
  codeReview: { status: "approved", minimum: 1, reviewIds: [5], reviewerIds: [123] }, planReview: { status: "approved", minimum: 1, reviewIds: [5], reviewerIds: [123] },
  freshness: { currentEligible: true, observedFrom: "2026-01-01T00:00:00Z", observedUntil: "2026-01-01T00:00:05Z", expiresAt: "2026-01-01T00:00:30Z", evaluatedAt: "2026-01-01T00:00:10Z", remoteFreshness: "historical-observation" }, blockers: [] };

describe("explicit immutable policy inputs", () => {
  it("projects only scope, policy CAS head, evidence identity and strict rules", () => {
    expect(policyPayload("p", "w", context, draft())).toEqual({ project: "p", workspace: "w", expectedPolicyHead: null, identityEvidenceId: "b".repeat(40),
      rules: { requiredChecks: [{ appId: 42, name: "exact check" }], reviewerIds: [123, 456], minimumCodeApprovals: 1, minimumPlanApprovals: 1, maxObservationAgeSeconds: 300 } });
  });
  it("refuses missing authority, evidence identity, empty or duplicate rules", () => {
    expect(() => policyPayload("p", "w", { ...context, canConfigure: false }, draft())).toThrow();
    for (const invalid of [{ identityEvidenceId: "fake" }, { checks: [] }, { checks: [{ appId: "42", name: "same" }, { appId: "42", name: "same" }] }, { reviewerIds: "" }, { reviewerIds: "123,123" }])
      expect(() => policyPayload("p", "w", context, { ...draft(), ...invalid })).toThrow();
  });
  it("rejects noninteger/unsafe account and app IDs, numeric coercion and invalid limits", () => {
    for (const value of ["true", "1e3", "1.1", "-2", "0", "9007199254740992"]) {
      expect(() => policyPayload("p", "w", context, { ...draft(), reviewerIds: value })).toThrow();
      expect(() => policyPayload("p", "w", context, { ...draft(), checks: [{ appId: value, name: "check" }] })).toThrow();
    }
    for (const invalid of [{ codeMinimum: "3" }, { planMinimum: "0" }, { age: "29" }, { age: "3601" }, { checks: Array.from({ length: 33 }, (_, i) => ({ appId: "42", name: String(i) })) }])
      expect(() => policyPayload("p", "w", context, { ...draft(), ...invalid })).toThrow();
  });
  it("binds confirmation to exact scope, action, CAS revision and rules", () => {
    const payload = policyPayload("p", "w", context, draft()), confirmation = policyConfirmation("activate", payload);
    expect(policyConfirmation("disable", payload)).not.toBe(confirmation);
    for (const patch of [{ project: "other" }, { workspace: "other" }, { expectedPolicyHead: "new" }, { rules: { ...payload.rules, maxObservationAgeSeconds: 30 } }])
      expect(policyConfirmation("activate", { ...payload, ...patch })).not.toBe(confirmation);
  });
});

describe("current policy freshness is never a historical badge", () => {
  it("derives conservative local expiry from server time including the read duration", () => {
    expect(policyDeadline(evaluation, 1000, 3000)).toBe(21000);
    expect(visiblePolicyStatus(evaluation, 21000, 20999)).toBe("satisfied");
    expect(visiblePolicyStatus(evaluation, 21000, 21000)).toBe("unknown");
    expect(policyDeadline(evaluation, 0, 25000)).toBe(25000);
  });
  it("invalidates pending/failed refresh and old scope/policy/PR status without reusing success", () => {
    expect(visiblePolicyStatus(evaluation, 30000, 1000, true)).toBe("unknown");
    expect(visiblePolicyStatus(null, 30000, 1000)).toBe("unknown");
    expect(visiblePolicyStatus({ ...evaluation, freshness: { ...evaluation.freshness, currentEligible: false } }, 30000, 1000)).toBe("unknown");
    expect(visiblePolicyStatus({ ...evaluation, freshness: { ...evaluation.freshness, expiresAt: null } }, 30000, 1000)).toBe("unknown");
  });
  it("does not turn disabled or absent policy into satisfaction", () => {
    expect(visiblePolicyStatus({ ...evaluation, status: "disabled" }, 0, 100)).toBe("disabled");
    expect(visiblePolicyStatus({ ...evaluation, status: "not_configured" }, 0, 100)).toBe("not_configured");
  });
  it("isolates asynchronous scope/action responses and serializes writes", async () => {
    const requests = new PolicyRequests(), first = requests.beginWrite()!;
    expect(requests.beginWrite()).toBeNull();
    let release!: () => void;
    const paints: string[] = [], delayed = new Promise<void>(resolve => { release = resolve; }).then(() => { if (first()) paints.push("old"); });
    requests.invalidate(); const current = requests.next(); if (current()) paints.push("current");
    release(); await delayed; requests.endWrite();
    expect(paints).toEqual(["current"]); expect(requests.beginWrite()).not.toBeNull();
  });
  it("renders expired result without a green class and escapes all server evidence", () => {
    const hostile = '<script>alert("x")</script>';
    const model = { value: { ...evaluation, checks: { ...evaluation.checks, required: [{ appId: 42, name: hostile, status: "passed", runId: 8 }] } },
      status: "unknown", prNumber: 10, invalidated: false, busy: false, error: "", refresh() {} } as unknown as PolicyStatusView;
    const html = renderToStaticMarkup(createElement(PolicyStatus, { model }));
    expect(html).not.toContain("review-policy__verdict--satisfied"); expect(html).not.toContain("<script>"); expect(html).toContain("&lt;script&gt;");
    expect(html).toContain("Platnost posledního vyhodnocení skončila"); expect(html).toContain("Aktuální splnění povinných kontrol není potvrzeno");
  });
  it("marks v1 evidence refresh required and historical assessment never uses a current green badge", () => {
    const html = renderToStaticMarkup(createElement(HistoricalPolicyAssessment, { evaluation, schemaVersion: 1 }));
    expect(html).toContain("Je nutné načíst nové pozorování"); expect(html).toContain("není ukazatelem aktuálního splnění"); expect(html).not.toContain("--satisfied");
  });
});

describe("single policy write", () => {
  it.each([403, 409, 428, 503])("does not retry HTTP %s and never supplies an actor", async code => {
    const calls: { url: string; init?: RequestInit }[] = [];
    const transport = (async (url, init) => { calls.push({ url: String(url), init }); return calls.length === 1 ? new Response("{}") : new Response('{"error":"declined"}', { status: code }); }) as typeof fetch;
    await expect(postPolicy("/policy", { project: "p" }, transport)).rejects.toThrow("declined");
    expect(calls).toHaveLength(2); expect(calls[0].url).toBe("/api/access/ui-session");
    expect(calls[1].init?.headers).toEqual({ "Content-Type": "application/json" });
  });
  it("does not retry an uncertain network failure", async () => {
    let calls = 0;
    const transport = (async () => { if (++calls === 1) return new Response("{}"); throw new Error("network"); }) as typeof fetch;
    await expect(postPolicy("/policy", {}, transport)).rejects.toThrow("network"); expect(calls).toBe(2);
  });
});
