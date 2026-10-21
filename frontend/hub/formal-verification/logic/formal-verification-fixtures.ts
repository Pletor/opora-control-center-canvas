import type { FormalRecord } from "./formal-verification";
export const formalScope = { project: "project", workspace: "workspace" };
export function formalFixture(): FormalRecord {
  const flags = { trust: "agent-reported" as const, sourceBinding: "agent-reported" as const, currentEligibility: false as const, independentlyVerified: false as const };
  return { ...formalScope, ...flags, id: "a".repeat(32), nodeId: "card", executionId: "b".repeat(32), epoch: 2,
    acceptedRevision: "c".repeat(40), assignmentDigest: "d".repeat(64), requestId: "request-1", requestDigest: "e".repeat(64), manifestDigest: "f".repeat(64),
    verification: { tool: { name: "tlc", version: "2.20", distributionSha256: "1".repeat(64) }, source: { repository: "owner/repo", commitSha: "2".repeat(40) },
      claims: [{ id: "invariant-1", kind: "invariant", statement: "No stale writer publishes", statementDigest: "3".repeat(64) }], assumptions: ["Finite state space"],
      configuration: { bounds: { workers: 2, attempts: 3 }, fairness: "weak", mode: "exhaustive" },
      artifacts: [{ path: "model/Lease.tla", role: "model", sha256: "4".repeat(64), bytes: 120, available: true }] },
    createdAt: "2026-10-21T10:00:00+00:00", report: { ...flags, requestId: "report-1", reportDigest: "5".repeat(64), outcome: "passed",
      checkedClaims: ["invariant-1"], summary: "Reported bounded model check only", artifacts: [{ path: "tlc.stdout", role: "stdout", sha256: "6".repeat(64), bytes: 40, available: true }],
      createdAt: "2026-10-21T10:01:00+00:00" } };
}
