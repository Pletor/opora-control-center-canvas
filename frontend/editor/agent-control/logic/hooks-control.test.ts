import { describe, expect, it } from "vitest";
import {
  bindingAvailability,
  canControlBinding,
  currentScope,
  isBindingInScope,
  isFreshScope,
  isUuid,
  parseAllowedPaths,
  scopeKey,
} from "./hooks-control";

describe("hooks-control – scoped form and safe labels", () => {
  it("keeps only non-empty relative allowed paths and removes duplicates", () => {
    expect(parseAllowedPaths("src\n\n./tests\nsrc\n  docs  ")).toEqual(["src", "./tests", "docs"]);
  });

  it("requires a real UUID instead of inferring a session from a name", () => {
    expect(isUuid("018f1514-3e6a-7db8-a05d-4e1ef4c769a2")).toBe(true);
    expect(isUuid("agent-alice")).toBe(false);
  });

  it("does not apply a late result from another project, workspace, or node", () => {
    const scope = currentScope("p1", "w1", "n1");
    expect(isFreshScope(scope, currentScope("p1", "w1", "n1"))).toBe(true);
    expect(isFreshScope(scope, currentScope("p2", "w1", "n1"))).toBe(false);
    expect(isFreshScope(scope, currentScope("p1", "w2", "n1"))).toBe(false);
    expect(isFreshScope(scope, currentScope("p1", "w1", "n2"))).toBe(false);
  });

  it("distinguishes generated settings from an observed hook", () => {
    expect(bindingAvailability({ hookObserved: false, state: "active" })).toBe("Připraveno · hook zatím nebyl pozorován");
    expect(bindingAvailability({ hookObserved: true, state: "active" })).toBe("Hook pozorován");
  });

  it("allows a verified binding to pause or request stop on a read-only card", () => {
    const observed = { hookObserved: true, state: "active" as const };
    expect(canControlBinding(false, observed, "pause")).toBe(true);
    expect(canControlBinding(true, observed, "pause")).toBe(true);
    expect(canControlBinding(true, observed, "stop")).toBe(true);
    expect(canControlBinding(true, observed, "resume")).toBe(false);
    expect(canControlBinding(true, { hookObserved: false, state: "active" }, "stop")).toBe(false);
    expect(canControlBinding(false, { hookObserved: true, state: "stopped" }, "stop")).toBe(false);
  });

  it("binding is in scope only for the captured card", () => {
    const scope = currentScope("p1", "w1", "n1");
    const binding = { project: "p1", workspace: "w1", nodeId: "n1" };
    expect(isBindingInScope(binding, scope)).toBe(true);
    expect(isBindingInScope({ ...binding, nodeId: "n2" }, scope)).toBe(false);
  });
});

describe("hooks-control – panel keys", () => {
  it("gives every panel part its own key for the same card", () => {
    const scope = currentScope("p", "w", "n");
    const keys = (["form", "lsp", "semantic"] as const).map((part) => scopeKey(part, scope));
    expect(new Set(keys).size).toBe(3);
    expect(scopeKey("form", currentScope("p", "w", "m"))).not.toBe(keys[0]);
  });
});
