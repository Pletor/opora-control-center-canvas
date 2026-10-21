import { STAGE_IDS, type AgentState, type AgentStage } from "./agent-state";

/** Pevný dokument ve tvaru schemaVersion 1 pro testy mapování (žádná ukázková data v UI). */
export function agentStateFixture(overrides: Partial<AgentState> = {}): AgentState {
  const head = "a".repeat(40);
  const health: Record<string, AgentStage["health"]> = { plan: "waiting", acceptance: "waiting", work: "blocking",
    pull_request: "not_connected", merge: "not_connected", plan_writeback: "not_connected" };
  return {
    schemaVersion: 1, generatedAt: "2026-10-21T09:12:40+00:00", projectId: "draft", workspaceId: "draft",
    heads: { acceptedHead: head, acceptedRevision: head, graphDigest: "g".repeat(64), workingDiffers: true,
      contextVersion: "c".repeat(64), budgetPolicyHead: { task_a: "p".repeat(40) } },
    stages: STAGE_IDS.map(id => ({ id, count: id === "plan" ? 4 : 1, health: health[id] ?? "ok", reason: id === "work" ? "lease_past_deadline" : "x_unknown" })),
    riskMix: { low: 2, elevated: 1, critical: 1 },
    decisions: [
      { id: "dec_1", kind: "accept_critical", targetId: "cs1", title: "Odebrat hranu", actionId: "act_1" },
      { id: "dec_2", kind: "review_result", targetId: "e".repeat(32), title: "Zkontrolovat nahlášený výsledek: A", actionId: "act_2" },
    ],
    actions: [
      { id: "act_1", verb: "accept", method: "POST", path: "/api/oporahub/graph-proposals/cs1/accept", targetId: "cs1",
        preconditions: { expectedAcceptedHead: head }, status: "blocked", blockReason: "human_only" },
      { id: "act_3", verb: "rebase", method: "POST", path: "/api/oporahub/changesets/cs0/rebase", targetId: "cs0",
        preconditions: { expectedAcceptedHead: head }, status: "ready" },
      { id: "act_4", verb: "claim", method: "POST", path: "/api/oporahub/executions/claim", targetId: "task_a",
        preconditions: { expectedAcceptedHead: head, previousExecutionId: null }, status: "ready", budget: { remainingAttempts: 2, remainingRepairRounds: 1 } },
      { id: "act_2", verb: "review", method: "GET", path: `/api/oporahub/executions/${"e".repeat(32)}/results`, targetId: "e".repeat(32),
        preconditions: { acceptedRevision: head }, status: "blocked", blockReason: "human_only" },
    ],
    gaps: [{ id: "ai_review", stage: "review", reason: "AI review chybí." }, { id: "pull_request_link", stage: "pull_request", reason: "Modul chybí." }],
    truncated: false, ...overrides,
  };
}
