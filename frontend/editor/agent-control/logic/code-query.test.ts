import { describe, expect, it } from "vitest";
import { currentScope, isFreshScope, lspProviderLabel, scopeKey } from "./code-query";

describe("code-query – scope of LSP and semantic questions", () => {
  it("does not apply a late result from another project, workspace, or node", () => {
    const scope = currentScope("p1", "w1", "n1");
    expect(isFreshScope(scope, currentScope("p1", "w1", "n1"))).toBe(true);
    expect(isFreshScope(scope, currentScope("p2", "w1", "n1"))).toBe(false);
    expect(isFreshScope(scope, currentScope("p1", "w2", "n1"))).toBe(false);
    expect(isFreshScope(scope, currentScope("p1", "w1", "n2"))).toBe(false);
  });

  it("gives every panel part its own key for the same card", () => {
    const scope = currentScope("p", "w", "n");
    expect(scopeKey("lsp", scope)).not.toBe(scopeKey("semantic", scope));
    expect(scopeKey("lsp", currentScope("p", "w", "m"))).not.toBe(scopeKey("lsp", scope));
  });

  it("labels provider status in Czech", () => {
    expect(lspProviderLabel("configured")).toBe("nakonfigurováno");
    expect(lspProviderLabel("unavailable")).toBe("nedostupné");
  });
});
