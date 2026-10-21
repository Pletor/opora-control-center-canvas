import { describe, expect, it } from "vitest";
import { agentStateFixture } from "@/hub/oporahub-agent-state/logic/fixtures";
import { defaultCard, initialHubLink } from "./hub-link";

describe("hub deep link", () => {
  it("reads the tab and card from the URL and defaults to the overview", () => {
    expect(initialHubLink("?environment=hub&ohView=agents")).toEqual({ tab: "agents", card: "" });
    expect(initialHubLink("?ohView=other&ohCard=task_a")).toEqual({ tab: "overview", card: "task_a" });
  });
  it("prefers the card offered for claim, then the first card", () => {
    expect(defaultCard(agentStateFixture(), [{ id: "x" }, { id: "task_a" }])).toBe("task_a");
    expect(defaultCard(agentStateFixture(), [{ id: "x" }])).toBe("x");
    expect(defaultCard(null, [])).toBe("");
  });
});
