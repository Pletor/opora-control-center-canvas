import { describe, expect, it } from "vitest";
import { agentStateFixture } from "@/hub/oporahub-agent-state/logic/fixtures";
import { defaultCard, initialHubLink, scopedContentLink } from "./hub-link";

describe("hub deep link", () => {
  it("opens native content review only for the exact project/workspace and immutable proposal ID", () => {
    const query = "?environment=hub&project=p&workspace=w&ohContent=" + "a".repeat(40);
    expect(scopedContentLink(query, "p", "w")).toBe("a".repeat(40));
    expect(scopedContentLink(query, "p", "other")).toBeNull();
    expect(scopedContentLink(query, "other", "w")).toBeNull();
    expect(scopedContentLink("?project=p&workspace=w&ohContent=../bad", "p", "w")).toBeNull();
  });
  it("reads the tab from the URL (the card deep link belongs to the card drawer) and defaults to the live process", () => {
    expect(initialHubLink("?environment=hub&ohView=agents")).toEqual({ tab: "agents" });
    expect(initialHubLink("?environment=hub&ohView=process")).toEqual({ tab: "process" });
    expect(initialHubLink("?ohView=other&ohCard=task_a")).toEqual({ tab: "process" });
    expect(initialHubLink("?ohView=overview")).toEqual({ tab: "process" });
  });
  it("prefers the card offered for claim, then the first card", () => {
    expect(defaultCard(agentStateFixture(), [{ id: "x" }, { id: "task_a" }])).toBe("task_a");
    expect(defaultCard(agentStateFixture(), [{ id: "x" }])).toBe("x");
    expect(defaultCard(null, [])).toBe("");
  });
});
