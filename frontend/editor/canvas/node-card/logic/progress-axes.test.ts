import { expect, it } from "vitest";
import { progressAxes } from "./progress-axes";
import { cardFace } from "@/editor/canvas/card-face/logic/card-face";
import type { ProgressEvidence } from "@/hub/oporahub-agent-state/logic/agent-state";
it("keeps an approved-looking prototype and merged workflow separate from functional proof", () => {
  const face = cardFace({ nodeId: "n", sector: false, decisions: [], nameOf: String,
    card: { nodeId: "n", stage: "plan_writeback", health: "ok", reason: "card_closed", executionId: "run", gate: { status: "ready", rule: null } } });
  const axes = progressAxes({ design: { artifactUrl: "/prototype", version: "v3" } }, face);
  expect(axes.map(axis => axis.value)).toEqual(["Podklad existuje", "Práce začleněna", "Nedolo\u017eeno"]);
  expect(progressAxes({ name: "[prototype] Login" }, face)[1].value).toBe("Nedoloženo");
  expect(axes[2].detail).toContain("konkr\u00e9tn\u00ed revize");
});

it("shows pin-checked functional evidence from the office without claiming independent verification", () => {
  const evidence: ProgressEvidence = { acceptedRevision: "current", designAccepted: true, verification: {
    verified: true, independent: false, level: "reported_evidence", source: "agent-reported execution receipt",
    acceptedRevision: "original", currentAcceptedRevision: "current", assignmentDigest: "digest", headSha: "sha", executionId: "run", receiptId: "receipt" } };
  const face = cardFace({ nodeId: "n", sector: false, decisions: [], nameOf: String,
    card: { nodeId: "n", stage: "review", health: "ok", reason: "human_review_required", executionId: "run", progressEvidence: evidence } });
  expect(progressAxes({}, face).map(axis => axis.value)).toEqual(["Přijatý", "Doložena Kanceláří", "Doloženo Kanceláří"]);
  expect(progressAxes({}, face)[2].detail).toContain("Nejde o nezávislé");
  expect(progressAxes({ name: "[prototype] Login" }, face)[2].value).toBe("Nedoloženo");
  evidence.verification!.currentAcceptedRevision = "stale";
  expect(progressAxes({}, face)[2].value).toBe("Nedoloženo");
});
it("does not promote metadata, unknown face, or progress to verification", () => {
  expect(progressAxes({}).every(axis => axis.value === "Nedolo\u017eeno")).toBe(true);
  const face = cardFace({ nodeId: "n", sector: false, decisions: [], nameOf: String,
    card: { nodeId: "n", stage: "work", health: "ok", reason: "runs_active", executionId: "run" } });
  expect(progressAxes({}, face)[1].value).toBe("Prob\u00edh\u00e1");
  expect(progressAxes({}, face)[2].value).toBe("Nedolo\u017eeno");
});
