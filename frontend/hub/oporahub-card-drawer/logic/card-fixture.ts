import { agentStateFixture } from "@/hub/oporahub-agent-state/logic/fixtures";

// Pevná data pro testy a náhled detailu karty (žádná ukázková data v UI): odpovědi API ve tvaru serveru
// pro jednu běžící kartu se sedmi kroky, otevřeným PR, nálezy a událostmi.
const head = "a".repeat(40);
const step = (n: number, title: string, kind: string, deps: number[], acceptance: string[]) =>
  ({ id: `s${n}`, order: n, title, kind, dependsOn: deps.map(d => `s${d}`), acceptance });
const steps = [
  step(1, "Schéma lease tabulky", "code", [], ["Migrace projde", "Index na node_id"]),
  step(2, "Claim endpoint vrací 409", "code", [1], ["Druhý claim vrátí 409", "Replay vrátí stejný lease", "Test souběhu"]),
  step(3, "Heartbeat a expirace", "code", [2], ["Heartbeat prodlouží lease", "Expirace po 90 s"]),
  step(4, "Obnova po výpadku", "code", [2], ["Expirovaný lease emituje lease.expired", "Po restartu serveru se lease obnoví z DB", "Test: výpadek 2× heartbeat uvolní kartu"]),
  step(5, "Integrační testy", "test", [3, 4], ["E2E claim → heartbeat → release", "Souběh dvou agentů"]),
  step(6, "Dokumentace protokolu", "docs", [5], ["docs/oporahub-executions.md"]),
  step(7, "Metriky lease", "code", [5], ["Počet expirací", "Délka lease"]),
];
const accepted = { goal: "Agent drží exkluzivní lease na kartu; bez heartbeat déle než 90 s se lease uvolní.",
  non_goals: "Distribuovaný zámek mezi více servery.", acceptance: "Druhý claim během platné lease vrátí 409\nLease vyprší po 90 s bez heartbeat\nHeartbeat každých 30 s", steps };
const working = { ...accepted, acceptance: "Druhý claim během platné lease vrátí 409\nLease vyprší po 90 s bez heartbeat\nHeartbeat každých 20 s, jitter ±5 s",
  steps: [...steps.slice(0, 3), { ...steps[3], acceptance: [...steps[3].acceptance.slice(0, 2), "Obnova z DB do 5 s"] }, ...steps.slice(4),
    step(8, "Alarm při 3 expiracích za hodinu", "code", [5], ["Alarm se spustí"])] };
const now = 1_792_636_000;
const at = (minute: number) => `2026-10-22T13:${String(minute).padStart(2, "0")}:00.000Z`;
const event = (id: number, minute: number, kind: string, extra: Record<string, unknown> = {}) => ({ id, at: at(minute), kind, projectId: "draft", workspaceId: "draft",
  nodeId: "card-lease", executionId: "ex0193", stepId: null, prNumber: null, stage: null, health: null, actor: { kind: "agent", name: "codex-2" }, data: {}, ...extra });

export function cardFixtureResponses(): Record<string, unknown> {
  const state = agentStateFixture({ cards: [{ nodeId: "card-lease", stage: "work", health: "ok", reason: "runs_active", executionId: "ex0193",
    kind: "code", layer: "backend", blockedBy: [], topoIndex: 1, nextActionId: "act_hb", gate: { status: "blocked", rule: "open_important_findings" },
    steps: { total: 7, done: 3, current: "s4" } } as never] });
  state.actions.push({ id: "act_hb", verb: "review.self_checks", method: "POST", path: "/api/oporahub/review-jobs/self-checks", targetId: "ex0193", preconditions: {}, status: "ready" });
  return {
    "/api/oporahub/agent-state": state,
    "/api/oporahub/changesets/context": { acceptedHead: head, graphDigest: "g", specificationsVersion: "v", workingDiffers: true, readOnly: false,
      documents: [{ nodeId: "card-lease", ownerWorkspace: "draft", revision: 4, fields: working }],
      acceptedDocuments: [{ nodeId: "card-lease", ownerWorkspace: "draft", revision: 3, fields: accepted }] },
    "/api/oporahub/changesets": { items: [
      { id: "cs-v3", parentRevision: "b".repeat(40), subject: "Návrh v3 (+s7)", by: { kind: "human", name: "Martin H." }, createdAt: "2026-10-21T13:50:00Z", accepted: true, changes: [{ nodeId: "card-lease" }] },
      { id: "cs-v4", parentRevision: head, subject: "Heartbeat 20 s + alarm", by: { kind: "agent", name: "planner" }, createdAt: "2026-10-22T14:05:00Z", accepted: false, changes: [{ nodeId: "card-lease" }] }] },
    "/api/oporahub/proposal-reviews": { risk: { level: "elevated", reasons: [], digest: "d" } },
    "/api/oporahub/executions": { executions: [{ executionId: "ex0193", project: "draft", workspace: "draft", nodeId: "card-lease", epoch: 212,
      acceptedRevision: head, assignmentDigest: "9f31c2" + "0".repeat(58), expiresAt: now + 252, serverNow: now, state: "running", createdAt: "2026-10-22T13:54:00Z", owner: "codex-2",
      budget: { policyHead: "p", familyId: "f", allocationId: "a", attempt: 1, repairRound: 0, kind: "initial", admittedAt: now - 2280, runDeadlineAt: now + 3120, maxRunSeconds: 5400 } }] },
    "/api/oporahub/executions/ex0193/results": { results: [{ receiptId: "r1", executionId: "ex0193", requestId: "q", state: "reported", acceptedRevision: head, assignmentDigest: "d", verification: "", createdAt: at(30),
      result: { summary: "s1–s3", stepResults: [
        { stepId: "s1", status: "done", evidence: { notes: "migrace", checks: ["pytest", "ruff", "tsc", "vitest"], commits: ["a1b2c3d"] } },
        { stepId: "s2", status: "done", evidence: { notes: "409", checks: ["pytest"], commits: ["b1", "c2"].map(x => x.padEnd(7, "0")) } },
        { stepId: "s3", status: "done", evidence: { notes: "expirace", checks: ["pytest"], commits: ["e4f5a6b"] } }] } }] },
    "/api/oporahub/execution-budgets": { project: "draft", workspace: "draft", nodeId: "card-lease", acceptedHead: head, canConfigure: true, unavailableReason: null, enrolled: true,
      policyHead: "p", policy: { limits: { maxRunSeconds: 5400, maxAttempts: 3, maxRepairRounds: 1 } }, family: null, attemptsUsed: 1, repairRoundsUsed: 0,
      remainingAttempts: 2, remainingRepairRounds: 1, latestExecutionId: "ex0193", blockedReason: null },
    "/api/oporahub/review-jobs/gates": { items: [{ executionId: "ex0193", cardId: "card-lease", repository: "opora/canvas", number: 145, headSha: "c0ffee1234567", prState: "open",
      reviewJobId: "j1", round: 1, riskTier: "standard", mergeReadiness: { template: { missing: [] }, requiredChecks: { ci: "pending" },
        selfChecks: { status: "missing", source: "agent", missing: ["lint"], failed: [], invalid: 0 }, base: { baseRef: "main", baseSha: "m", mergeBaseSha: null, behindBy: 2, fresh: false } },
      reviewGate: { status: "blocked", openImportant: 1, requiredHumanApprovals: 1, humanApprovalsAtHead: 0, reasons: ["open_important_findings", "required_checks_pending", "human_approvals_missing", "stale_against_main"],
        humans: { mode: "verified_humans", count: 0, identityIds: [], directorId: null, unverifiedApprovals: 0 } } }] },
    "/api/oporahub/review-jobs": { enabled: true, maxRounds: 3, jobs: [], findings: [
      { findingId: "f1", repository: "opora/canvas", number: 145, round: 1, severity: "important", status: "open", title: "Race mezi současným claim a expirací", path: "src/broker/lease.ts", line: 88 },
      { findingId: "f2", repository: "opora/canvas", number: 145, round: 1, severity: "medium", status: "fixed", title: "Chybí jitter v heartbeat", path: "", line: null }] },
    "/api/oporahub/events": { cursor: 18342, head: 18342, gap: false, events: [
      event(18300, 41, "changeset.proposed", { actor: { kind: "agent", name: "planner" }, data: { subject: "Návrh v3 (+s7)" } }),
      event(18301, 50, "changeset.accepted", { actor: { kind: "human", name: "Martin H." } }),
      event(18310, 54, "lease.claimed", { data: { epoch: 212 } }),
      event(18320, 58, "step.done", { stepId: "s3" }),
      event(18330, 59, "pr.linked", { prNumber: 145 }),
      event(18335, 59, "review.finding", { actor: { kind: "agent", name: "codex-review" }, data: { severity: "important", status: "open" } }),
      event(18342, 59, "step.started", { stepId: "s4" })] },
    "/api/oporahub/history/card/card-lease": { cardId: "card-lease", acceptedHead: head, items: [] },
    "/api/oporahub/blame/card/card-lease": { cardId: "card-lease", acceptedHead: head, items: [] },
    "/api/oporahub/verifications": { requests: [] },
    "/api/oporahub/auto-rebase/conflicts": { items: [] },
    "/api/oporahub/process": { items: [{ nodeId: "card-lease", acceptanceEvidence: false, doneConfirmed: false }] },
    "/api/access/ui-session": { ok: true },
  };
}
