import { expect, it } from "vitest";
import { asHumanRule, isAgentRule, ruleReviewBatchRequest, ruleReviewRequest } from "./agent-rule";

it("recognizes agent proposals and treats missing author as human", () => {
  expect(isAgentRule({ by: "agent" })).toBe(true);
  expect(isAgentRule({ by: "human" })).toBe(false);
  expect(isAgentRule({})).toBe(false);
});

it("drops the agent author when a human saves the rule", () => {
  const rule = { id: "r", text: "Old", kind: "must" as const, scope: "node" as const, target: "n", by: "agent" as const };
  expect(asHumanRule(rule, "New")).toEqual({ id: "r", text: "New", kind: "must", scope: "node", target: "n" });
  expect("by" in asHumanRule(rule)).toBe(false);
});

it("builds the rule-review request with the read proposal as CAS expectation", () => {
  const rule = { id: "r", text: "Návrh", kind: "must" as const, scope: "path" as const, target: "src", by: "agent" as const };
  expect(ruleReviewRequest("p1", "w1", rule, "approve")).toEqual({
    url: "/api/desktop-v3/rule-review",
    body: { project: "p1", workspace: "w1", id: "r", decision: "approve", expected: rule },
  });
});

it("builds one batch request with every selected proposal as its own CAS expectation", () => {
  const a = { id: "a", text: "A", kind: "must" as const, scope: "project" as const, target: "", by: "agent" as const };
  const b = { ...a, id: "b", scope: "node" as const, target: "n" };
  expect(ruleReviewBatchRequest("p1", "w1", [a, b], "reject")).toEqual({
    url: "/api/desktop-v3/rule-review-batch",
    body: { project: "p1", workspace: "w1", decision: "reject", items: [{ id: "a", expected: a }, { id: "b", expected: b }] },
  });
});
