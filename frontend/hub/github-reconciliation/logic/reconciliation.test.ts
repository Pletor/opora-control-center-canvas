import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { advanceHistory, controlPayload, enrollmentPayload, reconciliationLink, ReconciliationIntents, ReconciliationRequests,
  type ReconciliationBinding, type ReconciliationCandidate, type ReconciliationContext, type ReconciliationHistory, type ReconciliationItem } from "./reconciliation";
import { postReconciliation } from "./reconciliation-api";
import ReconciliationStatus from "../components/ReconciliationStatus";
import GithubReconciliation from "../components/GithubReconciliation";
import type { GithubReconciliationView } from "./use-github-reconciliation";

const binding: ReconciliationBinding = { id: "b", schemaVersion: 1, project: "p", workspace: "w", acceptedRevision: "a".repeat(40), identityEvidenceId: "e".repeat(40),
  repository: { id: 1, fullName: "owner/repo", baseBranch: "main" }, pr: { id: 2, number: 3, headRepoId: 4 }, enrolledHeadSha: "c".repeat(40), intervalSeconds: 300,
  by: { kind: "human", name: "Human" }, createdAt: "2026-01-01T00:00:00Z" };
const item: ReconciliationItem = { binding, control: { id: "control", bindingId: "b", parentControlId: null, generation: 1, action: "enroll", enabled: true, requestId: "request", by: binding.by, createdAt: binding.createdAt },
  job: { bindingId: "b", generation: 1, state: "scheduled", nextAttemptAt: binding.createdAt, leaseUntil: null, consecutiveFailures: 0, lastErrorCode: null, lastAttemptId: null, lastObservationId: null, lastEventId: null },
  latestAttempt: null, lastSuccessfulObservation: null, revisionRelation: { boundAcceptedRevision: binding.acceptedRevision, currentAcceptedRevision: binding.acceptedRevision, matchesCurrentAcceptedRevision: true } };
const context: ReconciliationContext = { project: "p", workspace: "w", currentAcceptedHead: binding.acceptedRevision, canConfigure: true, canPause: true,
  automaticWorkerEnabled: true, unavailableReason: null, serverNow: binding.createdAt, items: [item] };
const candidate: ReconciliationCandidate = { project: "p", workspace: "w", currentAcceptedHead: binding.acceptedRevision, canConfigure: true, unavailableReason: null,
  evidenceId: binding.identityEvidenceId, binding, existingEnabledBinding: null };

describe("durable enrollment authority inputs", () => {
  it("sends only current accepted head and scoped server evidence, not numeric identity/actor/outcome", () => {
    expect(enrollmentPayload("p", "w", context, candidate)).toEqual({ project: "p", workspace: "w", expectedAcceptedHead: binding.acceptedRevision, identityEvidenceId: binding.identityEvidenceId });
    expect(controlPayload("p", "w", item, "pause")).toEqual({ project: "p", workspace: "w", expectedGeneration: 1, action: "pause" });
  });
  it("refuses stale revision, missing authority, conflicting enabled binding and wrong scope", () => {
    for (const changed of [{ ...candidate, canConfigure: false }, { ...candidate, project: "other" }, { ...candidate, currentAcceptedHead: "old" }, { ...candidate, existingEnabledBinding: binding }])
      expect(() => enrollmentPayload("p", "w", context, changed)).toThrow();
    expect(() => enrollmentPayload("p", "w", { ...context, canConfigure: false }, candidate)).toThrow();
    expect(() => controlPayload("p", "other", item, "pause")).toThrow();
  });
  it("keeps a request ID for the same intent after uncertainty, but changes it for a new scope/generation/action", () => {
    let count = 0; const intents = new ReconciliationIntents(() => `request-${++count}`), payload = controlPayload("p", "w", item, "retry");
    expect(intents.request("retry:b", payload)).toBe("request-1");
    expect(intents.request("retry:b", { ...payload })).toBe("request-1");
    expect(intents.request("retry:b", { ...payload, expectedGeneration: 2 })).toBe("request-2");
    expect(intents.request("pause:b", payload)).toBe("request-3");
    expect(intents.request("pause:b", { ...payload, workspace: "other" })).toBe("request-4");
  });
  it("invalidates late reads/writes on scope or generation changes and blocks duplicate mutation clicks", async () => {
    const requests = new ReconciliationRequests(), valid = requests.beginWrite()!;
    expect(requests.beginWrite()).toBeNull();
    let finish!: () => void; const painted: string[] = [];
    const result = new Promise<void>(resolve => { finish = resolve; }).then(() => { if (valid()) painted.push("old scope"); });
    requests.invalidate(); finish(); await result; expect(painted).toEqual([]);
    requests.endWrite(); expect(requests.beginWrite()).not.toBeNull();
  });
});

describe("bounded independent history streams", () => {
  const first = { kind: "event", record: { id: "one" } }, second = { kind: "event", record: { id: "two" } };
  const attempt = { id: "attempt", state: "complete" as const, startedAt: binding.createdAt, finishedAt: binding.createdAt, errorCode: null, observationId: "o" };
  const page: ReconciliationHistory = { binding, items: [first, second], nextCursor: "20", attempts: [attempt], nextAttemptCursor: null };
  it("does not restart an exhausted records stream while loading attempts", () => {
    const result = advanceHistory({ items: [first], nextCursor: null, attempts: [], nextAttemptCursor: "2" }, page);
    expect(result.items).toEqual([first]); expect(result.nextCursor).toBeNull(); expect(result.attempts).toEqual([attempt]); expect(result.nextAttemptCursor).toBeNull();
  });
  it("deduplicates replayed page records and preserves exhausted attempts", () => {
    const result = advanceHistory({ items: [first], nextCursor: "1", attempts: [attempt], nextAttemptCursor: null }, page);
    expect(result.items).toEqual([first, second]); expect(result.attempts).toEqual([attempt]); expect(result.nextAttemptCursor).toBeNull();
  });
});

it("renders historical merged fact separately from failed current health, original plan and review", () => {
  const hostile = '<script>alert("x")</script>';
  const selected = { ...item, binding: { ...binding, repository: { ...binding.repository, fullName: hostile } }, job: { ...item.job, state: "retrying", lastErrorCode: hostile, consecutiveFailures: 1 },
    latestAttempt: { id: "failed", state: "failed", startedAt: binding.createdAt, finishedAt: binding.createdAt, errorCode: "unavailable", observationId: null },
    revisionRelation: { ...item.revisionRelation, currentAcceptedRevision: "new-plan", matchesCurrentAcceptedRevision: false },
    lastSuccessfulObservation: { id: "observation", bindingId: "b", createdAt: binding.createdAt, data: { complete: true, observedFrom: binding.createdAt, observedUntil: binding.createdAt, repository: binding.repository,
      pr: { ...binding.pr, baseRef: "main", headSha: "SOURCE-SHA", state: "merged", draft: false, merged: true, mergedAt: binding.createdAt, mergeCommitSha: "MERGE-SHA" } } } };
  const model = { context, selected, disabled: true, pauseAllowed: true, prepare() {} } as unknown as GithubReconciliationView;
  const html = renderToStaticMarkup(createElement(ReconciliationStatus, { model }));
  for (const text of ["Čeká na opakování", "Poslední úspěšné historické pozorování", "PR sloučen podle pozorování", "SOURCE-SHA", "MERGE-SHA", "new-plan", "Review a kontroly jsou samostatné", "&lt;script&gt;"]) expect(html).toContain(text);
  expect(html).not.toContain("<script>"); expect(html).not.toContain('href="javascript:');
  expect(html).toContain('>Pozastavit vybrané sledování</button>');
  expect(reconciliationLink({ ...binding, repository: { ...binding.repository, fullName: "https://evil.invalid" } })).toBeNull();
});

it("shows history with an empty Canvas and warns when the automatic worker is disabled", () => {
  const model = { context: { ...context, automaticWorkerEnabled: false }, items: [item], selected: item, busy: false, disabled: false, pauseAllowed: true, error: "",
    evidence: { items: [] }, evidenceId: "", candidate: { candidate: null, busy: false, error: "" }, review: null,
    history: { items: [{ kind: "event", record: { id: "preserved-event", toState: { state: "merged" } } }], attempts: [], nextCursor: null, nextAttemptCursor: null, busy: false, error: "", more() {} },
    prepare() {}, refresh() {}, select() {}, selectEvidence() {} } as unknown as GithubReconciliationView;
  const html = renderToStaticMarkup(createElement(GithubReconciliation, { model }));
  expect(html).toContain("preserved-event"); expect(html).toContain("Automatický serverový proces je v této instanci vypnutý");
});

describe("no implicit POST retry", () => {
  it.each([403, 409, 428, 503])("reports HTTP %s after one mutation without actor spoofing", async status => {
    const calls: RequestInit[] = [];
    const transport = (async (_url, init) => { calls.push(init ?? {}); return calls.length === 1 ? new Response("{}") : new Response('{"error":"declined"}', { status }); }) as typeof fetch;
    await expect(postReconciliation("/bindings", { requestId: "stable" }, transport)).rejects.toThrow("declined");
    expect(calls).toHaveLength(2); expect(calls[1].headers).toEqual({ "Content-Type": "application/json" }); expect(calls[1].body).toBe('{"requestId":"stable"}');
  });
  it("does not repeat an uncertain network mutation", async () => {
    let calls = 0; const transport = (async () => { if (++calls === 1) return new Response("{}"); throw new Error("uncertain"); }) as typeof fetch;
    await expect(postReconciliation("/bindings", {}, transport)).rejects.toThrow("uncertain"); expect(calls).toBe(2);
  });
});
