import { describe, expect, it } from "vitest";
import { checkLines, runView } from "./cell-view";
import { payloadLines } from "./gate-view";

describe("cell view", () => {
  it("lists planned checks, at most four, skipping broken items", () => {
    const checks = [{ id: "a", command: "pytest x" }, null, { id: 3 }, { id: "b", command: "npm test" },
      { id: "c", command: "node c.js" }, { id: "d", command: "uv run t" }, { id: "e", command: "py e" }];
    const lines = checkLines({ checks });
    expect(lines.map((l) => l.text)).toEqual(["kontroly: a `pytest x`", "kontroly: b `npm test`", "kontroly: c `node c.js`", "kontroly: d `uv run t`"]);
    expect(checkLines({})).toEqual([]);
    expect(checkLines(null)).toEqual([]);
  });

  it("reports a run as reported, never attested", () => {
    const actual = { tests: "fail", run: { executor: "A", verifier: "B", at: "2026-10-15T10:00:00+00:00",
      checks: [{ checkId: "a", command: "pytest", exitCode: 0, durationMs: 120, outputSha256: "x" },
        { checkId: "b", command: "npm test", exitCode: 1, durationMs: 5, outputSha256: "y" }] } };
    for (const payload of [{ actual, runTrust: "reported" }, { actual }]) {
      const view = runView(payload);
      expect(view?.badge).toBe("běh nahlášen – neatestováno");
      expect(view?.who).toBe("vykonal A · ověřil B");
      expect(view?.checks.map((c) => [c.passed, c.text])).toEqual([[true, "a · exit 0 (prošla) · 120 ms"], [false, "b · exit 1 (neprošla) · 5 ms"]]);
    }
    expect(JSON.stringify(runView({ actual }))).not.toMatch(/ověřeno bezpečně/);
  });

  it("has no run view without a run", () => {
    expect(runView({ actual: { tests: "pass" } })).toBeNull();
    expect(runView(undefined)).toBeNull();
  });

  it("keeps checks, run and runTrust out of the generic payload lines", () => {
    expect(payloadLines({ done: "x", checks: [{ id: "a", command: "pytest" }] })).toEqual(["hotovo: x"]);
    expect(payloadLines({ actual: { tests: "pass", run: { executor: "A" } }, runTrust: "reported" })).toEqual([]);
  });
});
