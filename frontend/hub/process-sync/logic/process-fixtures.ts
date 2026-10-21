import type { ProcessSnapshot } from "./process-sync";
export function processFixture(project = "draft", workspace = "draft"): ProcessSnapshot {
  return { schema: "opora.process-sync/1", project, workspace, acceptedRevision: "a".repeat(40),
    observedAt: "2026-10-21T12:00:00Z", cardLimit: 100, totalCards: 1, truncated: false,
    items: [{ nodeId: "task-1", name: "Kontrola změny", status: "ready", openIdeas: 1,
      nextAction: { kind: "claim", label: "Převzít kartu", reason: "Claim znovu ověří aktuálnost." },
      pipeline: { stageCount: 2, passedCount: 1, failedCount: 0, currentStage: "Kontrola" },
      workingMatchesAccepted: true, doneConfirmed: false, currentExecution: null,
      executionAvailability: { available: true, unavailableReason: null },
      links: { context: "/api/oporahub/executions/context", claim: "/api/oporahub/executions/claim",
        results: null, proposalContext: "/api/oporahub/changesets/context", brief: "/api/node-brief" } }],
    githubTracking: { scope: "workspace", limit: 100, truncated: false, items: [], reviews: [] } };
}
