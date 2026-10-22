import { describe, expect, it } from "vitest";
import { agentStateFixture } from "@/hub/oporahub-agent-state/logic/fixtures";
import { defaultCard, initialHubLink } from "./hub-link";

describe("hub deep link", () => {
  it("reads the tab from the URL (the card deep link belongs to the card drawer) and defaults to the overview", () => {
    expect(initialHubLink("?environment=hub&ohView=agents")).toEqual({ tab: "agents" });
    expect(initialHubLink("?ohView=other&ohCard=task_a")).toEqual({ tab: "overview" });
  });
  it("prefers the card offered for claim, then the first card", () => {
    expect(defaultCard(agentStateFixture(), [{ id: "x" }, { id: "task_a" }])).toBe("task_a");
    expect(defaultCard(agentStateFixture(), [{ id: "x" }])).toBe("x");
    expect(defaultCard(null, [])).toBe("");
  });
});
