import { expect, it } from "vitest";
import { parseAgentState } from "./agent-state";
import { agentStateFixture } from "./fixtures";

it("preserves typed worker evidence and rejects an independent-verification claim", () => {
  const card = { nodeId: "n", stage: "review" as const, health: "ok" as const, reason: "reported", executionId: "run",
    progressEvidence: { acceptedRevision: "a", designAccepted: true, verification: {
      verified: true, independent: false as const, level: "reported_evidence" as const, source: "agent-reported execution receipt",
      acceptedRevision: "a", assignmentDigest: "digest", headSha: "sha", executionId: "run", receiptId: "receipt" } } };
  const fixture = agentStateFixture({ cards: [card] });
  expect(parseAgentState(fixture, "draft", "draft").cards?.[0].progressEvidence).toEqual(card.progressEvidence);
  const invalid = structuredClone(fixture);
  Object.assign(invalid.cards![0].progressEvidence!.verification!, { independent: true });
  expect(() => parseAgentState(invalid, "draft", "draft")).toThrow();
});
