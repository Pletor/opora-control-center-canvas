import { describe, expect, it } from "vitest";
import { actionRows } from "./actions-model";
import { agentStateFixture } from "./fixtures";
import { loopModel } from "./loop-model";

describe("review gate labels", () => {
  it("names the gate rule reason of the review stage and the new agent actions", () => {
    const state = agentStateFixture();
    state.stages = state.stages.map(item => item.id === "review" ? { ...item, health: "waiting", reason: "stale_against_main" } : item);
    state.actions = [{ id: "act_x", verb: "pr.update_branch", method: "PUT", path: "github:/repos/o/r/pulls/7/update-branch",
      targetId: "e1", preconditions: { expectedHeadSha: "c".repeat(40) }, status: "ready" }];
    const review = loopModel(state).flatMap(item => item.kind === "stage" ? [item.stage] : []).find(item => item.id === "review")!;
    expect(review.reasonText).toBe("PR nestojí na aktuální hlavě cílové větve; čeká na aktualizaci.");
    expect(actionRows(state)[0].verbLabel).toBe("Aktualizovat větev PR");
  });
});
