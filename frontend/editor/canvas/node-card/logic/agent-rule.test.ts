import { expect, it } from "vitest";
import { asHumanRule, isAgentRule } from "./agent-rule";

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
